from sqlalchemy import text


async def audit(db, actor_id: int, action: str, target_id: int | None = None):
    await db.execute(text('INSERT INTO audit_events (actor_id, action, target_id) VALUES (:actor, :action, :target)'),
                     {'actor': actor_id, 'action': action, 'target': target_id})
