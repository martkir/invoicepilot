---
description: >-
  Simplification patterns for Django and Flask: database-level filtering with
  QuerySets, custom managers, and blueprint organization with thin routes.
metadata:
  tags: [python, Django, Flask, ORM, querysets, blueprints, patterns]
---

# Django and Flask Patterns

> FastAPI patterns live in [fastapi-structure.md](fastapi-structure.md) — dependency injection, response models, and the service layer are covered there against async SQLAlchemy and Pydantic v2.

## Django — QuerySet Methods

Filter in the database, not in Python. The loop below pulls every row into memory and discards most of them.

```python
# Before - filtering in Python
def get_active_premium_users():
    users = User.objects.all()
    result = []
    for user in users:
        if user.is_active and user.plan == "premium":
            result.append(user)
    return result

# After - database-level filtering
def get_active_premium_users():
    return User.objects.filter(is_active=True, plan="premium")
```

## Django — Manager Methods

When the same filter chain shows up in a third place, it belongs on a manager.

```python
# Before - repeated query logic
# In views.py
users = User.objects.filter(is_active=True, created_at__gte=last_week)

# In another_view.py
users = User.objects.filter(is_active=True, created_at__gte=last_week)

# After - custom manager
class UserManager(models.Manager):
    def recent_active(self, days=7):
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(is_active=True, created_at__gte=cutoff)

class User(models.Model):
    objects = UserManager()

# Usage
users = User.objects.recent_active()
```

## Flask — Blueprints and Thin Routes

Same principle as a FastAPI router: the view parses and delegates, the service owns the logic and the transaction.

```python
# Before - one module, logic inline in the view
@app.route("/users", methods=["POST"])
def create_user():
    data = request.get_json()
    user = User(email=data["email"], password_hash=bcrypt.hash(data["password"]))
    db.session.add(user)
    db.session.commit()
    return jsonify(id=user.id), 201

# After - blueprint, thin view, service owns the write
# app/users/routes.py
users_bp = Blueprint("users", __name__, url_prefix="/users")

@users_bp.route("", methods=["POST"])
def create_user():
    payload = UserCreate.model_validate(request.get_json())
    try:
        user = UserService(db.session).create(payload)
    except DuplicateUserError:
        return jsonify(detail="Email already registered"), 400
    return jsonify(UserResponse.model_validate(user).model_dump()), 201

# app/__init__.py
app.register_blueprint(users_bp)
```

Pydantic works fine outside FastAPI — using it for request validation keeps the view free of manual `data["key"]` access and gives the same error surface as the other frameworks.
