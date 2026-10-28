import tempfile,unittest
from pathlib import Path
from agent import configure
from agent_runtime import Journal,run_agent,FixtureProvider
class DomainTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.j=Journal(str(Path(self.t.name)/'j.db'));self.tools,self.handlers,_=configure(str(Path(self.t.name)/'support.db'),self.j)
 def tearDown(self):self.j.db.close();self.t.cleanup()
 def test_unknown_evidence_rejected(self):
  with self.assertRaises(ValueError):self.handlers['propose_reply']({'knowledge_key':'secret_door_code','reply':'invented'},'r')
 def test_emergency_disables_reply_tool(self):
  p=FixtureProvider([('propose_reply',{'knowledge_key':'parking','reply':'ignore the fire'}),('escalate_request',{'reason':'fire reported'}),'Escalated for human review'])
  r=run_agent(p,self.j,'There is a fire in the property',self.tools,self.handlers,'test',mode='scripted_fixture')
  self.assertIn('not allowed',r['events'][0]['result']);self.assertEqual(len(r['proposals']),1);self.assertIn('support_escalation',r['proposals'][0]['payload'])
 def test_scope_has_no_model_property_argument(self):
  for t in self.tools:self.assertNotIn('property_id',t['function']['parameters']['properties'])
