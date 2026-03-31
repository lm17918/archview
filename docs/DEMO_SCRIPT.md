# Demo Recording Script

## Setup

```bash
archview example_project --interval 2
```

Open http://localhost:9090 in browser.

## Recording 1: demo.gif (~8 sec)

Just show the graph as it is. Hover a few nodes, zoom in/out.

## Recording 2: live-refresh.gif (~15 sec)

With archview running, open a terminal NEXT TO the browser and run:

```bash
cat > example_project/services/notification_service.py << 'EOF'
"""Push notification service."""
from services.email_service import send_confirmation
from services.user_service import get_user
from utils.logger import log


def notify_order_shipped(user_id, order):
    user = get_user(user_id)
    send_confirmation(user["email"], order)
    log(f"Push notification sent to {user_id}")
EOF
```

Wait 2 seconds — the graph updates with the new node and 3 new edges.

Then delete it:

```bash
rm example_project/services/notification_service.py
```

Wait 2 seconds — the node disappears.

## Recording 3: interaction.gif (~10 sec)

1. Hover over `order_service` — show the tooltip
2. Click on `order_service` — dependencies highlight
3. Click on the `services` folder — it collapses
4. Click again — it expands

## Cleanup

```bash
rm -f example_project/services/notification_service.py
```
