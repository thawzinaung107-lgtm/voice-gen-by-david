"""Read-only staging inventory. No supplier balances become customer credits."""
import argparse
import json
import sqlite3
from pathlib import Path

def dry_run(path):
    source=Path(path).resolve()
    db=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)
    try:
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        result={'mode':'dry-run','source':str(source),'tables':{},'customer_credits_to_import':0,'supplier_balance_policy':'Preserve raw supplier balance only as external audit evidence; never credit customer wallets.'}
        for table in tables:
            quoted='"'+table.replace('"','""')+'"'
            columns=[r[1] for r in db.execute(f'PRAGMA table_info({quoted})')]
            result['tables'][table]={'rows':db.execute(f'SELECT count(*) FROM {quoted}').fetchone()[0],'columns':columns}
        # Preserve staging supplier charge/balance numeric values in a reviewable
        # audit manifest. They never produce wallet or ledger credit operations.
        result['supplier_financial_audit']=[]
        for table,meta in result['tables'].items():
            fields=[name for name in meta['columns'] if name in {'id','credits','balance','supplier_balance'}]
            financial=[name for name in fields if name!='id']
            if not financial: continue
            quoted='"'+table.replace('"','""')+'"'
            selected=','.join('"'+name+'"' for name in fields)
            for values in db.execute(f'SELECT {selected} FROM {quoted}'):
                result['supplier_financial_audit'].append({'source_table':table,'raw':dict(zip(fields,values)),'classification':'supplier audit only','customer_credit_delta':0})
        return result
    finally: db.close()

def main():
    p=argparse.ArgumentParser(); p.add_argument('database'); p.add_argument('--dry-run',action='store_true',required=True); args=p.parse_args()
    print(json.dumps(dry_run(args.database),indent=2))
if __name__=='__main__': main()
