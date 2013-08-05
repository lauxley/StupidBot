from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import settings
from basebot import ImproperlyConfigured, BaseCommand


class DbCommand(BaseCommand):
    def __init__(self, bot, ev):
        super(DbCommand, self).__init__(bot, ev)
        self.session = self.bot.Session()


class DbMixin(object):
    SCHEMA = None

    def __init__(self, *args, **kwargs):
        if self.SCHEMA is None:
            raise ImproperlyConfigured("A DbMixin plugin needs a schema.")
        super(DbMixin, self).__init__(*args, **kwargs)
        self._init_engine()
        self._make_table()

    def _init_engine(self):
        if not hasattr(settings, 'DB_BACKEND'):
            raise ImproperlyConfigured("A DbMixin plugin needs a DB_BACKEND setting.")
        if not hasattr(self.bot, 'engine') or self.bot.engine is None:
            self.bot.engine = create_engine(settings.DB_BACKEND, echo=True)
        if not hasattr(self.bot, 'Session') or self.bot.Session is None:
            self.bot.Session = sessionmaker(bind=self.bot.engine)

    def _make_table(self):
        self.SCHEMA.metadata.create_all(self.bot.engine)
