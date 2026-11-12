import logging
import os
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from .auth import Authenticator, digest
from .passwords import hash_password, verify_password
from .db import Database, one
from .evidence import validate as validate_evidence
from .logging_config import configure as configure_logging
from .ratelimit import SlidingWindowLimiter
from .service import now, reserve, serialize, approve, settle
from .storage import PrivateStorage

log = logging.getLogger('voicegen.requests')

class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid')
class SessionInput(Strict): access_token: str=Field(min_length=20,max_length=16384)
class AccountInput(Strict):
    email: str=Field(min_length=3,max_length=254,pattern=r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
    password: str=Field(min_length=12,max_length=200)
class GenerationInput(Strict):
    request_id: str=Field(pattern=r'^[A-Za-z0-9_-]{8,128}$')
    kind: str=Field(default='tts',pattern='^tts$')
    text: str=Field(min_length=1,max_length=10000)
    voice_id: str=Field(min_length=1,max_length=200)
    provider: str=Field(min_length=1,max_length=100)
    model_id: str=Field(min_length=1,max_length=100)
    language_code: str=Field(pattern='^(en|my)$')
    voice_settings: dict=Field(default_factory=dict)
class TopupInput(Strict):
    request_id: str=Field(pattern=r'^[A-Za-z0-9_-]{8,128}$')
    amount: int=Field(strict=True,gt=0,le=10000000)
    reference: str=Field(min_length=3,max_length=200)
class ApprovalInput(Strict): verification_reference: str=Field(min_length=8,max_length=200)
class ReconcileInput(Strict):
    outcome: str=Field(pattern='^(failed|completed)$')
    verification_reference: str=Field(min_length=8,max_length=200)

def create_app(env=None,auth=None,storage=None,database=None,limiter=None):
    env=dict(os.environ if env is None else env)
    origin=env['APP_ORIGIN'].rstrip('/')
    if not origin.startswith('https://'): raise ValueError('APP_ORIGIN must be HTTPS')
    db=database or Database(env['DATABASE_URL'])
    local=env.get('AUTH_MODE')=='local'
    auth=None if local else auth or Authenticator(env['SUPABASE_ISSUER'],env.get('SUPABASE_AUDIENCE','authenticated'),env['SUPABASE_JWKS_URL'])
    if storage is None and env.get('S3_BUCKET'): storage=PrivateStorage(env)
    limiter=limiter or SlidingWindowLimiter(env)
    configure_logging()
    if env.get('SENTRY_DSN'):
        try:
            import sentry_sdk
            sentry_sdk.init(dsn=env['SENTRY_DSN'], traces_sample_rate=0.0)
        except ImportError: pass
    app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
    app.state.db=db
    def rate_limit(request,name,key):
        try: limiter.check(name,str(key))
        except HTTPException as error:
            log.warning('rate limit exceeded',extra={'request_id':getattr(request.state,'request_id',None),'user_id':str(key),'path':request.url.path,'method':request.method,'status_code':429})
            return JSONResponse({'error':error.detail},429,headers=error.headers)
        return None
    @app.middleware('http')
    async def boundary(request,call_next):
        request.state.request_id=uuid.uuid4().hex
        start=time.monotonic()
        if request.headers.get('sec-fetch-site')=='cross-site': return JSONResponse({'error':'Cross-site request denied'},403)
        if request.method not in {'GET','HEAD','OPTIONS'} and request.headers.get('origin')!=origin:
            return JSONResponse({'error':'Origin required'},403)
        try: size=int(request.headers.get('content-length','0') or 0)
        except ValueError: return JSONResponse({'error':'Invalid content length'},400)
        if size<0 or size>6*1024*1024: return JSONResponse({'error':'Body too large'},413)
        if request.method not in {'GET','HEAD','OPTIONS'}:
            limit=5*1024*1024 if request.url.path.endswith('/evidence') else 65536
            body=bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body)>limit: return JSONResponse({'error':'Body too large'},413)
            request._body=bytes(body)
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Request-Id']=request.state.request_id
        duration=int((time.monotonic()-start)*1000)
        extra={'request_id':request.state.request_id,'path':request.url.path,'method':request.method,'status_code':response.status_code,'duration_ms':duration}
        if response.status_code>=500: log.error('request failed',extra=extra)
        elif response.status_code>=400: log.warning('request rejected',extra=extra)
        else: log.info('request',extra=extra)
        return response
    @app.exception_handler(HTTPException)
    async def errors(request,error): return JSONResponse({'error':error.detail},error.status_code)
    @app.exception_handler(IntegrityError)
    async def conflicts(request,error): return JSONResponse({'error':'Conflicting operation'},409)
    def identity(request):
        token=request.cookies.get('__Host-voicegen_session','')
        if not token: raise HTTPException(401,'Authentication required')
        with db.transaction(session_hash=digest(token)) as tx:
            session=one(tx,'SELECT * FROM sessions WHERE id=:s AND expires_at>now()',s=digest(token))
            if not session: raise HTTPException(401,'Session expired')
            return session['user_id']
    def admin(tx,user):
        if not one(tx,'SELECT is_admin FROM users WHERE id=:u',u=user)['is_admin']: raise HTTPException(403,'Administrator required')
    @app.get('/api/health')
    def health():
        if local: auth_public={'provider':'local'}
        else: auth_public={'provider':'supabase','url':env.get('SUPABASE_URL',''),'anonKey':env.get('SUPABASE_ANON_KEY','')}
        return {'ok':True,'configured':True,'mode':'production','auth':auth_public,'capabilities':{'auth':local or bool(env.get('SUPABASE_URL') and env.get('SUPABASE_ANON_KEY')),'manual_topups':storage is not None,'tts':False,'generation':False,'dialogue':False,'srt':False}}
    def client_ip(request):
        return request.client.host if request.client else 'unknown'
    @app.post('/api/session')
    def login(data:SessionInput,request:Request,response:Response):
        limited=rate_limit(request,'SESSION',client_ip(request))
        if limited: return limited
        claims=auth.verify(data.access_token)
        user=claims['sub']; token=secrets.token_urlsafe(48)
        expires=min(datetime.fromtimestamp(claims['exp'],timezone.utc),now()+timedelta(hours=12))
        with db.transaction(user=user) as tx:
            tx.execute(text('INSERT INTO users(id,email) VALUES(:u,:e) ON CONFLICT(id) DO NOTHING'),{'u':user,'e':claims.get('email')})
            tx.execute(text('INSERT INTO wallets(user_id) VALUES(:u) ON CONFLICT DO NOTHING'),{'u':user})
            tx.execute(text('INSERT INTO sessions(id,user_id,expires_at) VALUES(:s,:u,:e)'),{'s':digest(token),'u':user,'e':expires})
        response.set_cookie('__Host-voicegen_session',token,secure=True,httponly=True,samesite='strict',path='/',max_age=max(0,int((expires-now()).total_seconds())))
        return {'ok':True}
    def issue_session(response, user):
        token=secrets.token_urlsafe(48)
        expires=now()+timedelta(hours=12)
        with db.transaction(user=user) as tx:
            tx.execute(text('INSERT INTO sessions(id,user_id,expires_at) VALUES(:s,:u,:e)'),{'s':digest(token),'u':user,'e':expires})
        response.set_cookie('__Host-voicegen_session',token,secure=True,httponly=True,samesite='strict',path='/',max_age=12*60*60)
        return {'ok':True}
    @app.post('/api/account')
    def register(data:AccountInput,request:Request,response:Response):
        if not local: raise HTTPException(404,'Local accounts are disabled')
        limited=rate_limit(request,'SESSION',client_ip(request))
        if limited: return limited
        email=data.email.strip().lower()
        user=uuid.uuid4()
        try:
            with db.transaction(user=user) as tx:
                tx.execute(text('INSERT INTO users(id,email,password_hash) VALUES(:u,:e,:p)'),{'u':user,'e':email,'p':hash_password(data.password)})
                tx.execute(text('INSERT INTO wallets(user_id) VALUES(:u)'),{'u':user})
        except IntegrityError: raise HTTPException(409,'Account already exists') from None
        return issue_session(response, user)
    @app.post('/api/account/session')
    def local_login(data:AccountInput,request:Request,response:Response):
        if not local: raise HTTPException(404,'Local accounts are disabled')
        limited=rate_limit(request,'SESSION',client_ip(request))
        if limited: return limited
        email=data.email.strip().lower()
        with db.transaction() as tx:
            row=one(tx,'SELECT * FROM lookup_local_account(:e)',e=email)
        if not row or not verify_password(data.password, row['password_hash']): raise HTTPException(401,'Invalid email or password')
        return issue_session(response, row['id'])
    @app.delete('/api/session')
    def logout(request:Request,response:Response):
        hashed=digest(request.cookies.get('__Host-voicegen_session',''))
        with db.transaction(session_hash=hashed) as tx: tx.execute(text('DELETE FROM sessions WHERE id=:s'),{'s':hashed})
        response.delete_cookie('__Host-voicegen_session',secure=True,httponly=True,samesite='strict',path='/')
        return {'ok':True}
    def current_session(request):
        return digest(request.cookies.get('__Host-voicegen_session',''))
    @app.get('/api/sessions')
    def sessions(request:Request):
        user=identity(request)
        with db.transaction(user,session_hash=current_session(request)) as tx:
            return {'items':[{'id':r['id'],'createdAt':int(r['created_at'].timestamp()*1000),'expiresAt':int(r['expires_at'].timestamp()*1000),'current':r['id']==current_session(request)} for r in tx.execute(text('SELECT id,created_at,expires_at FROM sessions WHERE user_id=:u AND expires_at>now() ORDER BY created_at DESC'),{'u':user}).mappings()]}
    @app.delete('/api/sessions/{ident}')
    def revoke_session(ident:str,request:Request):
        user=identity(request)
        with db.transaction(user,session_hash=current_session(request)) as tx:
            result=tx.execute(text('DELETE FROM sessions WHERE id=:id AND user_id=:u'),{'id':ident,'u':user})
            if result.rowcount==0: raise HTTPException(404,'Session not found')
            return {'ok':True}
    @app.delete('/api/sessions')
    def revoke_others(request:Request):
        user=identity(request); current=current_session(request)
        with db.transaction(user,session_hash=current) as tx:
            result=tx.execute(text('DELETE FROM sessions WHERE user_id=:u AND id!=:s'),{'u':user,'s':current})
            return {'ok':True,'revoked':result.rowcount}
    @app.get('/api/me')
    def me(request:Request):
        user=identity(request)
        with db.transaction(user) as tx:
            u=one(tx,'SELECT id,email,is_admin FROM users WHERE id=:u',u=user)
            w=one(tx,'SELECT * FROM wallets WHERE user_id=:u',u=user)
            return {'user':{'id':str(user),'email':u['email'],'isAdmin':u['is_admin']},'wallet':{'balance':w['available'],'available':w['available'],'reserved':w['reserved'],'source':'application'}}
    @app.get('/api/voices')
    def voices(request:Request): identity(request); return {'voices':[],'hasMore':False}
    @app.post('/api/generate')
    def generate(data:GenerationInput,request:Request):
        user=identity(request)
        limited=rate_limit(request,'GENERATE',user)
        if limited: return limited
        if env.get('SUPPLIER_ENABLED')!='true': raise HTTPException(503,'Supplier integration is not verified; generation disabled')
        rate=int(env.get('CREDIT_PER_CHARACTER','0'))
        if rate<=0: raise HTTPException(503,'Pricing unavailable')
        with db.transaction(user) as tx: result=serialize(reserve(tx,user,data.model_dump(),rate))
        return {'generation':result}
    @app.get('/api/history')
    def history(request:Request):
        user=identity(request)
        with db.transaction(user) as tx: return {'items':[serialize(r) for r in tx.execute(text('SELECT * FROM generations WHERE user_id=:u ORDER BY created_at DESC LIMIT 200'),{'u':user}).mappings()]}
    def owned(tx,user,ident):
        row=one(tx,'SELECT * FROM generations WHERE id=:id AND user_id=:u',id=ident,u=user)
        if not row: raise HTTPException(404,'Generation not found')
        return row
    @app.get('/api/history/{ident}')
    def detail(ident:uuid.UUID,request:Request):
        user=identity(request)
        with db.transaction(user) as tx: return {'generation':serialize(owned(tx,user,ident))}
    def stream(key,request,head=False):
        if storage is None: raise HTTPException(503,'Private storage unavailable')
        from botocore.exceptions import ClientError
        try: obj=storage.get(key,request.headers.get('range'))
        except ClientError as error:
            code=error.response.get('Error',{}).get('Code')
            raise HTTPException(416 if code=='InvalidRange' else 404,'Object unavailable') from None
        headers={'Content-Length':str(obj['ContentLength']),'Accept-Ranges':'bytes'}
        if obj.get('ContentRange'): headers['Content-Range']=obj['ContentRange']
        status=206 if obj.get('ContentRange') else 200
        body=obj['Body']
        if head: body.close(); return Response(status_code=status,headers=headers)
        def chunks():
            try:
                while chunk:=body.read(65536): yield chunk
            finally: body.close()
        return StreamingResponse(chunks(),status_code=status,media_type=obj.get('ContentType','application/octet-stream'),headers=headers)
    @app.api_route('/api/audio/{ident}',methods=['GET','HEAD'])
    def audio(ident:uuid.UUID,request:Request):
        user=identity(request)
        with db.transaction(user) as tx: row=owned(tx,user,ident)
        if row['expires_at']<=now(): raise HTTPException(410,'Audio expired')
        if row['state']!='completed' or not row['object_key']: raise HTTPException(404,'Audio unavailable')
        return stream(row['object_key'],request,request.method=='HEAD')
    @app.post('/api/topups')
    def topup(data:TopupInput,request:Request):
        user=identity(request)
        limited=rate_limit(request,'TOPUP',user)
        if limited: return limited
        with db.transaction(user) as tx:
            # Wallet lock provides stable duplicate behavior.
            one(tx,'SELECT * FROM wallets WHERE user_id=:u FOR UPDATE',u=user)
            row=one(tx,'SELECT * FROM topups WHERE user_id=:u AND request_id=:r',u=user,r=data.request_id)
            if row:
                if row['amount']!=data.amount or row['reference']!=data.reference: raise HTTPException(409,'request_id payload conflict')
            else: row=one(tx,'INSERT INTO topups(id,user_id,request_id,amount,reference) VALUES(:id,:u,:r,:a,:ref) RETURNING *',id=uuid.uuid4(),u=user,r=data.request_id,a=data.amount,ref=data.reference)
            return {'topup':dict(row)}
    @app.get('/api/topups')
    def topups(request:Request):
        user=identity(request)
        with db.transaction(user) as tx: return {'items':[dict(r) for r in tx.execute(text('SELECT * FROM topups WHERE user_id=:u ORDER BY created_at DESC LIMIT 200'),{'u':user}).mappings()]}
    @app.put('/api/topups/{ident}/evidence')
    async def evidence(ident:uuid.UUID,request:Request):
        user=identity(request)
        limited=rate_limit(request,'EVIDENCE',user)
        if limited: return limited
        if storage is None: raise HTTPException(503,'Private storage unavailable')
        data=bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data)>5*1024*1024: raise HTTPException(413,'Evidence too large')
        content_type=request.headers.get('content-type','')
        signatures={'image/png':b'\x89PNG\r\n\x1a\n','image/jpeg':b'\xff\xd8\xff','application/pdf':b'%PDF-'}
        if content_type not in signatures or not data.startswith(signatures[content_type]): raise HTTPException(415,'PNG, JPEG or PDF evidence required')
        with db.transaction(user) as tx:
            row=one(tx,'SELECT * FROM topups WHERE id=:id AND user_id=:u FOR UPDATE',id=ident,u=user)
            if not row: raise HTTPException(404,'Topup not found')
            if row['state']!='pending': raise HTTPException(409,'Approved evidence immutable')
            if not validate_evidence(content_type,bytes(data),user=user,topup=ident):
                tx.execute(text("UPDATE topups SET evidence_state='rejected' WHERE id=:id"),{'id':ident})
                rejected=True
            else: rejected=False
            if not rejected:
                key=storage.key(user,ident,'evidence'); storage.put(key,bytes(data),content_type)
                tx.execute(text("UPDATE topups SET evidence_key=:k,evidence_state='clean' WHERE id=:id"),{'id':ident,'k':key})
        if rejected: raise HTTPException(415,'Evidence failed content validation')
        return {'ok':True}
    @app.get('/api/admin/topups')
    def admin_topups(request:Request):
        user=identity(request)
        limited=rate_limit(request,'ADMIN',user)
        if limited: return limited
        with db.transaction(user) as tx:
            admin(tx,user)
            return {'items':[dict(r) for r in tx.execute(text('SELECT * FROM topups ORDER BY created_at DESC LIMIT 200')).mappings()]}
    @app.get('/api/admin/topups/{ident}/evidence')
    def admin_evidence(ident:uuid.UUID,request:Request):
        user=identity(request)
        limited=rate_limit(request,'ADMIN',user)
        if limited: return limited
        with db.transaction(user) as tx:
            admin(tx,user); row=one(tx,'SELECT * FROM topups WHERE id=:id',id=ident)
            if not row or not row['evidence_key']: raise HTTPException(404,'Evidence not found')
        response=stream(row['evidence_key'],request)
        response.headers['Content-Disposition']='attachment; filename="payment-evidence"'
        response.headers['Content-Security-Policy']="sandbox; default-src 'none'"
        return response
    @app.post('/api/admin/topups/{ident}/approve')
    def approval(ident:uuid.UUID,data:ApprovalInput,request:Request):
        user=identity(request)
        limited=rate_limit(request,'ADMIN',user)
        if limited: return limited
        with db.transaction(user) as tx:
            admin(tx,user); result=approve(tx,user,ident,data.verification_reference)
            return {'topup':dict(result)}
    @app.post('/api/admin/generations/{ident}/reconcile')
    def reconcile(ident:uuid.UUID,data:ReconcileInput,request:Request):
        import json
        user=identity(request)
        limited=rate_limit(request,'ADMIN',user)
        if limited: return limited
        with db.transaction(user) as tx:
            admin(tx,user)
            row=one(tx,'SELECT * FROM generations WHERE id=:id FOR UPDATE',id=ident)
            if not row: raise HTTPException(404,'Generation not found')
            if str(row['user_id'])==str(user): raise HTTPException(403,'Independent administrator required')
            if row['state'] in {'failed','completed'}:
                if row['state']!=data.outcome: raise HTTPException(409,'Terminal outcome conflict')
                return {'generation':serialize(row)}
            if row['state']!='uncertain' and not (row['state']=='pending' and row['expires_at']<=now()): raise HTTPException(409,'Only uncertain or expired pending jobs require reconciliation')
            if data.outcome=='completed' and not row['object_key']: raise HTTPException(409,'Completed reconciliation requires privately stored audio')
            row=settle(tx,ident,data.outcome=='completed')
            tx.execute(text("INSERT INTO admin_audit(actor_id,action,target_id,details) VALUES(:a,'reconcile',:id,CAST(:d AS jsonb))"),{'a':user,'id':ident,'d':json.dumps(data.model_dump())})
            return {'generation':serialize(row)}
    return app
