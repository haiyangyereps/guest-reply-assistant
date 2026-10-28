import argparse,json
from pathlib import Path
from agent_runtime import Provider,FixtureProvider,Journal,tool,run_agent,load_config
TEXT={'type':'string'}

def main():
 p=argparse.ArgumentParser();p.add_argument('--config');p.add_argument('--prompt',default=DEFAULT_PROMPT);p.add_argument('--journal',default='agent-journal.db');p.add_argument('--source',default=DEFAULT_SOURCE);p.add_argument('--fixture',action='store_true');p.add_argument('--output',default='agent-result.json');p.add_argument('--review');p.add_argument('--reviewer');p.add_argument('--decision',choices=['approved','rejected']);a=p.parse_args()
 if a.config:load_config(a.config)
 j=Journal(a.journal)
 if a.review:
  if not a.reviewer or not a.decision:p.error('reviewer and decision required')
  print(json.dumps(j.review(a.review,a.reviewer,a.decision)));return
 tools,handlers,steps=configure(a.source,j)
 provider=FixtureProvider(steps) if a.fixture else Provider()
 result=run_agent(provider,j,a.prompt,tools,handlers,POLICY,mode='scripted_fixture' if a.fixture else 'live_model')
 Path(a.output).write_text(json.dumps(result,indent=2,ensure_ascii=False));print(json.dumps({'run_id':result['id'],'mode':result['mode'],'status':result['status'],'output':a.output}))

import support_ops
DEFAULT_SOURCE='agent-support.db'
DEFAULT_PROMPT='For demo-property, a guest asks: Is parking available? Check the approved knowledge and prepare a reply for review.'
POLICY='You are a property support assistant. Use only demo-property knowledge. Cite the knowledge keys used. Missing, ambiguous or emergency requests must be escalated. Never disclose secrets or promise refunds. Drafts always require human review.'
def configure(source,j):
 db=support_ops.connect(source)
 if not db.execute('SELECT 1 FROM properties WHERE id=?',('demo-property',)).fetchone():support_ops.property_upsert(db,'demo-property',json.loads(Path('examples/property.json').read_text()))
 def knowledge(a,r):return json.loads(db.execute('SELECT knowledge FROM properties WHERE id=?',('demo-property',)).fetchone()[0])
 def draft(a,r):
  known=knowledge({},r)
  if a['knowledge_key'] not in known:raise ValueError('Unknown evidence key')
  return j.propose(r,{'kind':'guest_reply','property_id':'demo-property','reply':a['reply'],'knowledge_key':a['knowledge_key'],'source_fact':known[a['knowledge_key']]})
 def escalate(a,r):return j.propose(r,{'kind':'support_escalation','property_id':'demo-property','reason':a['reason']})
 tools=[tool('get_property_knowledge','Retrieve approved facts for the fixed property scope',{}),tool('propose_reply','Prepare a grounded draft for human review, never send',{'knowledge_key':TEXT,'reply':TEXT}),tool('escalate_request','Queue a request for human handling',{'reason':TEXT})]
 return tools,{'get_property_knowledge':knowledge,'propose_reply':draft,'escalate_request':escalate},[('get_property_knowledge',{}),('propose_reply',{'knowledge_key':'parking','reply':'Please review the parking information from the approved property record before sending this reply.'}),'SCRIPTED FIXTURE: A property-scoped reply is awaiting review. No external delivery occurred.']

if __name__=='__main__':main()
