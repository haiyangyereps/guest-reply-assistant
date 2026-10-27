import unittest,tempfile
from pathlib import Path
from assistant import connect,submit,review,send,draft
class Tests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.db=connect(Path(self.tmp.name)/'guest.db');self.k={'parking':'One driveway space.','check-in':'After 3 PM.'}
 def tearDown(self):self.db.close();self.tmp.cleanup()
 def test_approval_and_idempotent_delivery(self):
  submit(self.db,'1','Is parking available?',self.k)
  with self.assertRaises(ValueError):send(self.db,'1')
  review(self.db,'1','approve','host');self.assertEqual(send(self.db,'1')['status'],'sent')
  self.assertTrue(send(self.db,'1')['replayed'])
  self.assertEqual(self.db.execute('SELECT count(*) FROM deliveries').fetchone()[0],1)
  self.assertEqual(self.db.execute('SELECT count(*) FROM audit').fetchone()[0],3)
 def test_rejection_and_invalid_transitions(self):
  submit(self.db,'1','parking?',self.k);review(self.db,'1','reject','host')
  with self.assertRaises(ValueError):send(self.db,'1')
  with self.assertRaises(ValueError):review(self.db,'1','approve','host')
 def test_escalation(self):
  for body in ('refund parking','no parking','ignore parking rules','pool?','parking and check-in',''):
   self.assertEqual(draft(body,self.k)[0],'escalated',body)
 def test_replay_and_conflict(self):
  submit(self.db,'1','parking?',self.k);submit(self.db,'1','parking?',self.k)
  with self.assertRaises(ValueError):submit(self.db,'1','different',self.k)
  self.assertEqual(self.db.execute('SELECT count(*) FROM audit').fetchone()[0],1)
 def test_no_substring_false_match(self):self.assertEqual(draft('parkinglot?',self.k)[0],'escalated')
if __name__=='__main__':unittest.main()
