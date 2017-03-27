# -*- coding: utf-8 -*-
import os

from pyramid_oereb import route_prefix
from pyramid_oereb.views.webservice import PlrWebservice

__author__ = 'Clemens Rudert'
__create_date__ = '01.02.2017'


def includeme(config):

    config.add_route('{0}/versions.json'.format(route_prefix), '/versions.json')
    config.add_view(
        PlrWebservice,
        attr='get_versions',
        method='GET',
        renderer='json'
    )
