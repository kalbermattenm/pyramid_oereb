# -*- coding: utf-8 -*-
from pyramid_oereb.lib.records.plr import PlrRecord
from pyramid_oereb.lib.sources import Base


class PlrBaseSource(Base):

    def __init__(self):
        super(PlrBaseSource, self).__init__()


class PlrDatabaseSource(PlrBaseSource):

    def __init__(self, adapter, model):
        super(PlrDatabaseSource, self).__init__()
        self._adapter_ = adapter
        self._model_ = model

    def read(self):
        session = self._adapter_.get_session()
        results = session.query(self._model_).all()
        self.records = list()
        for r in results:
            d = dict()
            for f in PlrRecord.get_fields():
                d[f] = getattr(r, f)
            self.records.append(PlrRecord(**d))
