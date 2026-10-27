"""Deterministic FAQ workflow with persistent review, approval and a local send adapter."""
import argparse
import json
import re
import sqlite3
from datetime import datetime, timezone

def connect(path):
    db=sqlite3.connect(path);db.row_factory=sqlite3.Row
    db.executescript('''CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY,body TEXT, status TEXT,draft TEXT,reason TEXT);
    CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,message_id TEXT,action TEXT,actor TEXT,created TEXT);
    CREATE TABLE IF NOT EXISTS deliveries(message_id TEXT PRIMARY KEY,body TEXT);''');return db

def log(db,key,action,actor):
    db.execute('INSERT INTO audit(message_id,action,actor,created) VALUES(?,?,?,?)',(key,action,actor,datetime.now(timezone.utc).isoformat()))

def draft(body,knowledge):
    text=body.lower()
    if not body.strip():return 'escalated',None,'empty request'
    if re.search(r'\b(refund|emergency|cancel|fire|injury|unsafe|police|password)\b',text):return 'escalated',None,'sensitive request'
    if re.search(r'\b(not|no|never|cannot|can.t|ignore|override)\b',text):return 'escalated',None,'ambiguous or unsupported instruction'
    hits=[answer for key,answer in knowledge.items() if re.search(r'(?<!\w)'+re.escape(key.lower())+r'(?!\w)',text)]
    if len(hits)!=1:return 'escalated',None,'requires clarification or unsupported topic'
    return 'pending','Hello! '+hits[0],'knowledge match; human review required'

def submit(db,key,body,knowledge):
    if not key.strip() or not isinstance(body,str):raise ValueError('message ID and text required')
    with db:
        row=db.execute('SELECT * FROM messages WHERE id=?',(key,)).fetchone()
        if row:
            if row['body']!=body:raise ValueError('message ID reused with different text')
            return dict(row)
        state,reply,reason=draft(body,knowledge)
        db.execute('INSERT INTO messages VALUES(?,?,?,?,?)',(key,body,state,reply,reason));log(db,key,'submitted','system')
    return dict(db.execute('SELECT * FROM messages WHERE id=?',(key,)).fetchone())

def review(db,key,action,actor):
    if action not in ('approve','reject') or not actor.strip():raise ValueError('review action and named actor required')
    with db:
        target='approved' if action=='approve' else 'rejected'
        c=db.execute("UPDATE messages SET status=? WHERE id=? AND status='pending'",(target,key))
        if not c.rowcount:raise ValueError('only pending drafts can be reviewed')
        log(db,key,action,actor)

def send(db,key):
    # Atomic local sink; a real inbox needs its own idempotency/reconciliation adapter.
    with db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT * FROM messages WHERE id=?',(key,)).fetchone()
        if not row:raise ValueError('unknown message')
        if row['status']=='sent':return {'status':'sent','replayed':True}
        if row['status']!='approved':raise ValueError('approval required before sending')
        db.execute('INSERT INTO deliveries VALUES(?,?)',(key,row['draft']))
        db.execute("UPDATE messages SET status='sent' WHERE id=?",(key,));log(db,key,'local_delivery','system')
    return {'status':'sent','adapter':'local SQLite sink; no external message sent'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--db',default='guest.db');s=p.add_subparsers(dest='command',required=True)
    a=s.add_parser('submit');a.add_argument('id');a.add_argument('message');a.add_argument('--knowledge',default='examples/property.json')
    a=s.add_parser('review');a.add_argument('id');a.add_argument('action',choices=['approve','reject']);a.add_argument('--actor',required=True)
    a=s.add_parser('send');a.add_argument('id')
    s.add_parser('status');a=p.parse_args();db=connect(a.db)
    try:
        if a.command=='submit':
            with open(a.knowledge) as f:knowledge=json.load(f)
            result=submit(db,a.id,a.message,knowledge)
        elif a.command=='review':review(db,a.id,a.action,a.actor);result={'reviewed':a.id}
        elif a.command=='send':result=send(db,a.id)
        else:result={'messages':[dict(x) for x in db.execute('SELECT * FROM messages')],'audit':[dict(x) for x in db.execute('SELECT * FROM audit')]}
        print(json.dumps(result,indent=2))
    finally:db.close()
if __name__=='__main__':main()
