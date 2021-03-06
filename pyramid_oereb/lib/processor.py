# -*- coding: utf-8 -*-
import logging

from sqlalchemy.orm.exc import NoResultFound

from pyramid_oereb.lib.records.documents import DocumentRecord
from pyramid_oereb.lib.records.plr import PlrRecord


log = logging.getLogger('pyramid_oereb')


class Processor(object):

    def __init__(self, real_estate_reader, municipality_reader, exclusion_of_liability_reader,
                 glossary_reader, plr_sources, extract_reader):
        """
        The Processor class is directly bound to the get_extract_by_id service in this application. It's task
        is to unsnarl the difficult model of the oereb extract and handle all objects inside this extract
        correctly. In addition it provides an easy to use method interface to access the information.
        It is also used to wrap all accessors in one point to have a processing interface.

        Args:
            real_estate_reader (pyramid_oereb.lib.readers.real_estate.RealEstateReader): The
                real estate reader instance for runtime use.
            municipality_reader (pyramid_oereb.lib.readers.municipality.MunicipalityReader): The
                municipality reader instance for runtime use.
            exclusion_of_liability_reader
                (pyramid_oereb.lib.readers.exclusion_of_liability.ExclusionOfLiabilityReader):
                The exclusion of liability reader instance for runtime use.
            glossary_reader (pyramid_oereb.lib.readers.glossary.GlossaryReader): The glossary
                reader instance for runtime use.
            plr_sources (list of pyramid_oereb.standard.sources.plr.DatabaseSource): The
                public law restriction source instances for runtime use wrapped in a list.
            extract_reader (pyramid_oereb.lib.readers.extract.ExtractReader): The extract reader
                instance for runtime use.
        """
        self._real_estate_reader_ = real_estate_reader
        self._municipality_reader_ = municipality_reader
        self._exclusion_of_liability_reader_ = exclusion_of_liability_reader
        self._glossary_reader_ = glossary_reader
        self._plr_sources_ = plr_sources
        self._extract_reader_ = extract_reader

    def filter_published_documents(self, record):
        """
        Filter only published documents.

        Args:
            record (pyramid_oereb.lib.records.plr.PlrRecord or
                pyramid_oereb.lib.records.documents.DocumentRecord): The public law restriction or
                document record.
        """
        published_docs = list()
        if isinstance(record, PlrRecord):
            for doc in record.documents:
                if doc.published:
                    doc = self.filter_published_documents(doc)
                    published_docs.append(doc)
            record.documents = published_docs
        elif isinstance(record, DocumentRecord):
            for doc in record.references:
                if doc.published:
                    doc = self.filter_published_documents(doc)
                    published_docs.append(doc)
            record.references = published_docs
        return record

    def plr_tolerance_check(self, extract):
        """
        The function checking if the found plr results exceed the minimal surface or length
        value defined in the configuration and should therefor be represented in the extract
        or considered 'false trues' and be removed from the results.

        Args:
            extract (pyramid_oereb.lib.records.extract.ExtractRecord): The extract in it's
                unvalidated form

        Returns:
            pyramid_oereb.lib.records.extract.ExtractRecord: Returns the updated extract
        """

        real_estate = extract.real_estate
        inside_plrs = []
        outside_plrs = []

        for public_law_restriction in real_estate.public_law_restrictions:
            if isinstance(public_law_restriction, PlrRecord) and public_law_restriction.published:
                # Test if the geometries list is now empty - if so remove plr from plr list
                if public_law_restriction.calculate(real_estate):
                    inside_plrs.append(self.filter_published_documents(public_law_restriction))
                else:
                    outside_plrs.append(public_law_restriction)

        # Check if theme is concerned
        def is_inside_plr(theme_code):
            for plr in inside_plrs:
                if plr.theme.code == theme_code:
                    return True
            return False

        # Ensure ConcernedThemes contains only inside PLRs
        themes_to_move = []
        for i, theme in enumerate(extract.concerned_theme):
            if not is_inside_plr(theme.code):
                themes_to_move.append(i)
        themes_to_move.reverse()
        for idx in themes_to_move:
            extract.not_concerned_theme.append(extract.concerned_theme.pop(idx))

        real_estate.public_law_restrictions = self.get_legend_entries(inside_plrs, outside_plrs)
        return extract

    @staticmethod
    def view_service_handling(real_estate, images, format):
        """
        Handles all view service related stuff. In the moment this is:
            * construction of the correct url (reference_wms) depending on the real estate
            * downloading of the image if parameter was set

        Args:
            real_estate (pyramid_oereb.lib.records.real_estate.RealEstateRecord):
                The real estate record to be updated.
            images (bool): Switch whether the images should be downloaded or not.
            format (string): The format currently used. For 'pdf' format,
                the used map size will be adapted to the pdf format,

        Returns:
            pyramid_oereb.lib.records.real_estate.RealEstateRecord: The updated extract.
        """
        real_estate.plan_for_land_register.get_full_wms_url(real_estate, format)
        if images:
            real_estate.plan_for_land_register.download_wms_content()

        for public_law_restriction in real_estate.public_law_restrictions:
            public_law_restriction.view_service.get_full_wms_url(real_estate, format)
            if images:
                public_law_restriction.view_service.download_wms_content()
        return real_estate

    @staticmethod
    def get_legend_entries(inside_plrs, outside_plrs):
        """
        We need to apply the right legend entries to each plr record which is intersecting the real estate.
        This means to make a topic wise grouping and find every legend entry which is on one hand not the same
        type code as the intersecting plr itself and on the other hand the same type code as the non
        intersecting one. We finally need to attach all this criteria matching legend entries to *the*
        intersecting one.

        Args:
            inside_plrs (list of pyramid_oereb.lib.records.plr.PlrRecord): The PLR's which are intersecting
                the real estate
            outside_plrs (list of pyramid_oereb.lib.records.plr.PlrRecord): The PLR's which are in the BBOX
                of the view but not intersecting the real estate
        Returns:
            list of pyramid_oereb.lib.records.plr.PlrRecord: The updated records with the hopefully correct
                legend entries assigned.
        """

        # for each plr which has intersection with the real estate
        for inside_plr in inside_plrs:
            # we clean its related legend entries, because it has its own entry stored via its symbol
            #  attribute
            inside_plr.view_service.legends = []
            # for every plr outside of the real estate
            for outside_plr in outside_plrs:
                # we check if it is belonging to the same theme
                if inside_plr.theme.code == outside_plr.theme.code:
                    # if it is we look up every legend related to this outside plr
                    for legend in outside_plr.view_service.legends:
                        # we check if the legend type code is not the same as the intersected plr ones and
                        # the legend type code is the same as the outside plr ones
                        if inside_plr.type_code != legend.type_code and \
                                outside_plr.type_code == legend.type_code:
                            # at this point we have a legend entry which has different type code then the
                            # intersecting plr, but before we can append this we need to check if a item is
                            # already in the list. Therefor we use a self made method.
                            inside_plr.view_service.unique_update_legends(legend)

        return inside_plrs

    @property
    def real_estate_reader(self):
        """
        Returns:
            pyramid_oereb.lib.readers.real_estate.RealEstateReader: The real estate reader
            instance.
        """
        return self._real_estate_reader_

    @property
    def municipality_reader(self):
        """
        Returns:
            pyramid_oereb.lib.readers.municipality.MunicipalityReader: The municipality reader
            reader instance.
        """
        return self._municipality_reader_

    @property
    def exclusion_of_liability_reader(self):
        """
        Returns:
            pyramid_oereb.lib.readers.exclusion_of_liability.ExclusionOfLiabilityReader:
            The exclusion of liability reader reader instance.
        """
        return self._exclusion_of_liability_reader_

    @property
    def glossary_reader(self):
        """
        Returns:
            pyramid_oereb.lib.readers.glossary.GlossaryReader: The glossary reader reader
            instance.
        """
        return self._glossary_reader_

    @property
    def plr_sources(self):
        """
        Returns:
            list of pyramid_oereb.lib.sources.plr.DatabaseSource: The list of plr
            source instances.
        """
        return self._plr_sources_

    @property
    def extract_reader(self):
        """
        Returns:
            pyramid_oereb.lib.readers.extract.ExtractReader: The extract reader instance.
        """
        return self._extract_reader_

    def process(self, real_estate, params, sld_url):
        """
        Central processing method to hook in from webservice.

        Args:
            real_estate (pyramid_oereb.lib.records.real_estate.RealEstateRecord): The real
                estate reader to obtain the real estates record.
            params (pyramid_oereb.views.webservice.Parameter): The parameters of the extract
                request.
            sld_url (str): The URL which provides the sld to style and filter the highlight of the real
                estate.

        Returns:
            pyramid_oereb.lib.records.extract.ExtractRecord: The generated extract record.
        """
        municipalities = self._municipality_reader_.read()
        exclusions_of_liability = self._exclusion_of_liability_reader_.read()
        glossaries = self._glossary_reader_.read()
        for municipality in municipalities:
            if municipality.fosnr == real_estate.fosnr:
                if not municipality.published:
                    raise NotImplementedError  # TODO: improve message
                extract_raw = self._extract_reader_.read(real_estate, municipality.logo, params)
                # the selection of view services will be done whilst tolerance check. This enables us to take
                # care about the circumstance that after tolerance check plrs will be dismissed which were
                # recognized as intersecting before. To avoid this the tolerance check is gathering all plrs
                # intersecting and not intersecting and starts the legend entry sorting after.
                extract = self.plr_tolerance_check(extract_raw)
                self.view_service_handling(extract.real_estate, params.images, params.format)

                extract.exclusions_of_liability = exclusions_of_liability
                extract.glossaries = glossaries
                # obtain the highlight wms url and its content only if the parameter full was requested (PDF)
                if params.flavour == 'full':
                    extract.real_estate.set_highlight_url(sld_url)
                return extract
        raise NoResultFound()
