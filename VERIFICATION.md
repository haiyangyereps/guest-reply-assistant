# Local verification

Fictional sample data; commands executed successfully. Temporary database paths shown below are ephemeral.

```text
python3 assistant.py --db /var/folders/zg/sd0lgkgn0q71mm5sgl66mkkc0000gn/T/tmpy88ixv7h/guest.db submit demo-1 Is parking available?
{
  "id": "demo-1",
  "body": "Is parking available?",
  "status": "pending",
  "draft": "Hello! One parking space is available in the driveway.",
  "reason": "knowledge match; human review required"
}
```

```text
python3 assistant.py --db /var/folders/zg/sd0lgkgn0q71mm5sgl66mkkc0000gn/T/tmpy88ixv7h/guest.db review demo-1 approve --actor demo-host
{
  "reviewed": "demo-1"
}
```

```text
python3 assistant.py --db /var/folders/zg/sd0lgkgn0q71mm5sgl66mkkc0000gn/T/tmpy88ixv7h/guest.db send demo-1
{
  "status": "sent",
  "adapter": "local SQLite sink; no external message sent"
}
```
