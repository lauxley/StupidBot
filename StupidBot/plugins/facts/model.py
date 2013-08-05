from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Date

Base = declarative_base()


class Fact(Base):
    """
    type : ['fact', 'quote', 'date']
    """
    __tablename__ = 'facts'

    id = Column(Integer, primary_key=True)
    type = Column(String(length=20))
    category = Column(String(length=20))
    date = Column(Date)
    author = Column(String(length=40))
    text = Column(String(length=255))

    def __repr__(self):
        if self.type == 'quote':
            return u'%s said: %s' % (self.author, self.text)
        elif self.type == 'date':
            return u'%s: %s' % (self.date, self.text)
        return u'%s' % self.text
