# -*- coding: utf-8 -*-
from pyramid_oereb.lib.sources import BaseDatabaseSource
from pyramid_oereb.lib.records.view_service import LegendEntryRecord
from pyramid_oereb.lib.sources.legend import LegendBaseSource


class DatabaseSource(BaseDatabaseSource, LegendBaseSource):

    def read(self, **kwargs):
        """
        Central method to read one legend entry.

        Args:
            (kwargs): Arbitrary keyword arguments. It must contain the key 'type_code'.
        """
        session = self._adapter_.get_session(self._key_)
        try:
            query = session.query(self._model_)
            if kwargs.get('type_code'):
                results = query.filter(
                    self._model_.type_code == kwargs.get('type_code')
                ).all()
            else:
                raise AttributeError('Necessary parameter is missing.')

            self.records = list()
            for result in results:
                self.records.append(LegendEntryRecord(
                    result.symbol,
                    result.legend_text,
                    result.type_code,
                    result.type_code_list,
                    result.theme
                ))
        finally:
            session.close()
