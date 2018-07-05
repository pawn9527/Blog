from orm import Model, IntegerField, StringField, FloatField, TextField, BooleanField
import time, uuid


def next_id():
    return "%015d%s000" % (int(time.time() * 1000), uuid.uuid4().hex)


class User(Model):
    __table__ = 'users'
    id = StringField(primary_key=True, default=next_id, ddl="varchar(50)")
    name = StringField(ddl="varchar(50)")
    email = StringField(ddl="varchar(50)")
    password = StringField(ddl="varchar(50)")
    admin = BooleanField()
    image = StringField(ddl='varchar(500)')
    create_time = FloatField(default=time.time)


class Blog(Model):
    __table__ = "blog"

    id = StringField(primary_key=True, default=next_id, ddl="varchar(50)")
    user_id = StringField(ddl="varchar(50)")
    user_name = StringField(ddl="varchar(50)")
    user_image = StringField(ddl='varchar(500)')
    name = StringField(ddl="varchar(50)")
    summary = StringField(ddl="varchar(100)")
    content = TextField()
    create_time = FloatField(default=time.time)


class Comment(Model):
    __table__ = "comments"

    id = StringField(primary_key=True, default=next_id, ddl="varchar(50)")
    blog_id = StringField(ddl="varchar(50)")
    user_id = StringField(ddl="varchar(50)")
    user_name = StringField(ddl="varchar(50)")
    user_image = StringField(ddl="varchar(500)")
    content = TextField()
    create_time = FloatField(default=time.time)
