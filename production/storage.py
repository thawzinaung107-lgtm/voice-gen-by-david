import re
import uuid
import boto3
from botocore.config import Config
from fastapi import HTTPException

class PrivateStorage:
    def __init__(self,env):
        self.bucket=env['S3_BUCKET']
        self.client=boto3.client('s3',endpoint_url=env['S3_ENDPOINT_URL'],aws_access_key_id=env['S3_ACCESS_KEY_ID'],aws_secret_access_key=env['S3_SECRET_ACCESS_KEY'],region_name='auto',config=Config(signature_version='s3v4',retries={'max_attempts':2}))
    @staticmethod
    def key(user,ident,purpose):
        if purpose not in {'audio','evidence'}: raise ValueError('purpose')
        return f"{purpose}/{uuid.UUID(str(user))}/{uuid.UUID(str(ident))}/{uuid.uuid4().hex}"
    def put(self,key,data,content_type):
        self.client.put_object(Bucket=self.bucket,Key=key,Body=data,ContentType=content_type,Metadata={'private':'true'})
    def get(self,key,byte_range=None):
        args={'Bucket':self.bucket,'Key':key}
        if byte_range:
            if not re.fullmatch(r'bytes=(?:[0-9]+-[0-9]*|-[0-9]+)',byte_range): raise HTTPException(416,'Invalid byte range')
            args['Range']=byte_range
        return self.client.get_object(**args)
