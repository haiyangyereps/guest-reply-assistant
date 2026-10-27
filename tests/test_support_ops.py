import tempfile,unittest
from pathlib import Path
from support_ops import connect,property_upsert,receive,act,queue
class SupportTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.db=connect(Path(self.t.name)/'support.db');property_upsert(self.db,'A',{'parking':'Use driveway A.'});property_upsert(self.db,'B',{'parking':'Use garage B.'})
 def tearDown(self):self.db.close();self.t.cleanup()
 def test_property_isolation_and_conflict(self):
  self.assertIn('driveway A',receive(self.db,'a','A','parking?',now=0)['draft'])
  self.assertIn('garage B',receive(self.db,'b','B','parking?',now=0)['draft'])
  with self.assertRaises(ValueError):receive(self.db,'a','B','parking?',now=0)
  with self.assertRaises(ValueError):receive(self.db,'c','unknown','parking?',now=0)
 def test_urgent_sla(self):
  r=receive(self.db,'a','A','Emergency fire',now=0);self.assertEqual(r['due'],900);self.assertEqual(r['status'],'escalated');self.assertIsNone(r['draft']);self.assertEqual(queue(self.db,now=901)['summary']['sla_breaches'],1)
 def test_human_response_and_resolution(self):
  receive(self.db,'a','A','refund?',now=0)
  act(self.db,'a',1,'host','human_reply','I will review this personally.',now=10)
  act(self.db,'a',2,'host','approve',now=20);act(self.db,'a',3,'host','deliver',now=30);act(self.db,'a',4,'host','resolve',now=40)
  self.assertEqual(queue(self.db,now=50)['summary']['mean_first_response_seconds'],30)
  with self.assertRaises(ValueError):act(self.db,'a',5,'host','deliver')
  self.assertEqual(self.db.execute('SELECT count(*) FROM ticket_deliveries').fetchone()[0],1)
 def test_stale_version_and_approval_guard(self):
  receive(self.db,'a','A','parking?',now=0)
  with self.assertRaises(ValueError):act(self.db,'a',1,'host','deliver')
  act(self.db,'a',1,'host','assign','agent-a')
  with self.assertRaises(ValueError):act(self.db,'a',1,'host','approve')
 def test_sla_breach_is_historical(self):
  receive(self.db,'a','A','parking?',now=0);act(self.db,'a',1,'host','approve',now=10);act(self.db,'a',2,'host','deliver',now=15000)
  self.assertEqual(queue(self.db,now=20000)['summary']['sla_breaches'],1)
if __name__=='__main__':unittest.main()
