"""Property-scoped support triage, SLA queue, reviewed responses and local resolution."""
import argparse,json,time
from pathlib import Path
from assistant import connect as base_connect,draft

def connect(path):
 db=base_connect(path);db.executescript('''CREATE TABLE IF NOT EXISTS properties(id TEXT PRIMARY KEY,knowledge TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS tickets(id TEXT PRIMARY KEY,property_id TEXT NOT NULL,body TEXT NOT NULL,priority TEXT NOT NULL,status TEXT NOT NULL,draft TEXT,reason TEXT,owner TEXT NOT NULL DEFAULT 'unassigned',created REAL NOT NULL,due REAL NOT NULL,first_response REAL,resolved REAL,version INTEGER NOT NULL DEFAULT 1);
 CREATE TABLE IF NOT EXISTS ticket_audit(id INTEGER PRIMARY KEY,ticket_id TEXT,actor TEXT,action TEXT,created REAL,details TEXT);
 CREATE TABLE IF NOT EXISTS ticket_deliveries(ticket_id TEXT PRIMARY KEY,reply TEXT,created REAL);''');return db

def audit(db,key,actor,action,now,details=''):
 if not isinstance(actor,str) or not actor.strip() or len(actor)>100:raise ValueError('named actor required')
 db.execute('INSERT INTO ticket_audit(ticket_id,actor,action,created,details) VALUES(?,?,?,?,?)',(key,actor,action,now,details))

def property_upsert(db,key,knowledge):
 if not isinstance(key,str) or not key.strip() or not isinstance(knowledge,dict) or not knowledge:raise ValueError('property ID and nonempty knowledge required')
 if any(not isinstance(k,str) or not k.strip() or not isinstance(v,str) or not v.strip() for k,v in knowledge.items()):raise ValueError('knowledge requires nonempty string keys and values')
 with db:db.execute('INSERT INTO properties VALUES(?,?) ON CONFLICT(id) DO UPDATE SET knowledge=excluded.knowledge',(key,json.dumps(knowledge)))

def receive(db,key,property_id,body,now=None):
 now=time.time() if now is None else now
 if not isinstance(key,str) or not key.strip() or not isinstance(body,str) or not 0<len(body)<=8000:raise ValueError('ticket ID and message up to 8000 characters required')
 with db:
  db.execute('BEGIN IMMEDIATE');previous=db.execute('SELECT * FROM tickets WHERE id=?',(key,)).fetchone()
  if previous:
   if previous['body']!=body or previous['property_id']!=property_id:raise ValueError('ticket ID reused with different message or property')
   return dict(previous)
  prop=db.execute('SELECT knowledge FROM properties WHERE id=?',(property_id,)).fetchone()
  if not prop:raise ValueError('unknown property; no fallback knowledge is used')
  state,reply,reason=draft(body,json.loads(prop['knowledge']))
  import re
  urgent=bool(re.search(r'\b(fire|injury|unsafe|emergency|police)\b',body.lower()))
  priority='urgent' if urgent else 'normal';sla=900 if urgent else 14400
  db.execute('INSERT INTO tickets(id,property_id,body,priority,status,draft,reason,created,due) VALUES(?,?,?,?,?,?,?,?,?)',(key,property_id,body,priority,'needs_review' if state=='pending' else 'escalated',reply,reason,now,now+sla));audit(db,key,'system','received',now)
 return dict(db.execute('SELECT * FROM tickets WHERE id=?',(key,)).fetchone())

def act(db,key,version,actor,action,text='',now=None):
 now=time.time() if now is None else now
 with db:
  db.execute('BEGIN IMMEDIATE');r=db.execute('SELECT * FROM tickets WHERE id=?',(key,)).fetchone()
  if not r or r['version']!=version:raise ValueError('unknown ticket or stale version')
  if r['status']=='resolved':raise ValueError('resolved tickets are read-only')
  values={'owner':r['owner'],'status':r['status'],'draft':r['draft'],'first_response':r['first_response'],'resolved':r['resolved']}
  if action=='assign':
   if not isinstance(text,str) or not 1<=len(text.strip())<=100:raise ValueError('owner required')
   values['owner']=text.strip()
  elif action=='approve':
   if r['status']!='needs_review':raise ValueError('only reviewable drafts can be approved')
   values['status']='approved'
  elif action=='human_reply':
   if not isinstance(text,str) or not 1<=len(text.strip())<=4000:raise ValueError('human reply required')
   if r['status'] not in ('needs_review','escalated'):raise ValueError('reply cannot change after approval or delivery')
   values['draft']=text.strip();values['status']='needs_review'
  elif action=='deliver':
   if r['status']!='approved':raise ValueError('approval required')
   db.execute('INSERT INTO ticket_deliveries VALUES(?,?,?)',(key,r['draft'],now));values['status']='responded';values['first_response']=now
  elif action=='resolve':
   if r['status']!='responded':raise ValueError('record a response before resolving')
   values['status']='resolved';values['resolved']=now
  else:raise ValueError('unknown action')
  db.execute('UPDATE tickets SET owner=:owner,status=:status,draft=:draft,first_response=:first_response,resolved=:resolved,version=version+1 WHERE id=:id',{**values,'id':key});audit(db,key,actor,action,now,text)
 return dict(db.execute('SELECT * FROM tickets WHERE id=?',(key,)).fetchone())

def queue(db,now=None):
 now=time.time() if now is None else now
 rows=[dict(r) for r in db.execute('SELECT * FROM tickets')]
 for r in rows:r['sla_breached']=(r['first_response'] if r['first_response'] is not None else now)>r['due']
 responded=[r for r in rows if r['first_response'] is not None]
 return {'summary':{'tickets':len(rows),'unanswered':sum(r['first_response'] is None for r in rows),'urgent_open':sum(r['priority']=='urgent' and r['status']!='resolved' for r in rows),'sla_breaches':sum(r['sla_breached'] for r in rows),'resolved':sum(r['status']=='resolved' for r in rows),'mean_first_response_seconds':sum(r['first_response']-r['created'] for r in responded)/len(responded) if responded else None},'tickets':sorted(rows,key=lambda r:(r['status']=='resolved',r['priority']!='urgent',r['due']))}

def main():
 p=argparse.ArgumentParser();p.add_argument('--db',default='support.db');s=p.add_subparsers(dest='cmd',required=True)
 a=s.add_parser('property');a.add_argument('id');a.add_argument('knowledge')
 a=s.add_parser('receive');a.add_argument('id');a.add_argument('property');a.add_argument('message')
 a=s.add_parser('act');a.add_argument('id');a.add_argument('version',type=int);a.add_argument('action',choices=['assign','approve','human_reply','deliver','resolve']);a.add_argument('--actor',required=True);a.add_argument('--text',default='')
 s.add_parser('queue');a=p.parse_args();db=connect(a.db)
 try:
  if a.cmd=='property':property_upsert(db,a.id,json.loads(Path(a.knowledge).read_text()));out={'property':a.id}
  elif a.cmd=='receive':out=receive(db,a.id,a.property,a.message)
  elif a.cmd=='act':out=act(db,a.id,a.version,a.actor,a.action,a.text)
  else:out=queue(db)
  print(json.dumps(out,indent=2))
 finally:db.close()
if __name__=='__main__':main()
