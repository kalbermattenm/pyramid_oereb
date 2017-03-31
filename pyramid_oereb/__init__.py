# -*- coding: utf-8 -*-

import logging

from pyramid_oereb.lib.adapter import DatabaseAdapter
from pyramid_oereb.lib.config import ConfigReader
from pyramid.config import Configurator

from pyramid_oereb.lib.config import parse
from pyramid_oereb.lib.readers.real_estate import RealEstateReader

__version__ = '0.0.1'


log = logging.getLogger('pyramid_oereb')
route_prefix = None
config_reader = None
database_adapter = None


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application. This is necessary for development of
    your plugin. So you can run it local with the paster server and in a IDE like PyCharm. It
    is intended to leave this section as is and do configuration in the includeme section only.
    Push additional configuration in this section means it will not be used by the production
    environment at all!
    """
    config = Configurator(settings=settings)
    config.include('pyramid_oereb', route_prefix='oereb')
    config.scan()
    return config.make_wsgi_app()


def includeme(config):
    """
    By including this in your pyramid web app you can easily provide a running OEREB Server

    :param config: The pyramid apps config object
    :type config: Configurator
    """
    global route_prefix, config_reader, database_adapter

    # Set route prefix
    route_prefix = config.route_prefix

    # Get settings
    settings = config.get_settings()

    # Load configuration file
    cfg_file = settings.get('pyramid_oereb.cfg.file', None)
    cfg_section = settings.get('pyramid_oereb.cfg.section', None)
    config_reader = ConfigReader(cfg_file, cfg_section)
    real_estate_config = config_reader.get_real_estate_config()

    # initially instantiate database adapter for global session handling
    database_adapter = DatabaseAdapter()


    real_estate_reader = RealEstateReader(
        real_estate_config.get('source').get('class'),
        **real_estate_config.get('source').get('params')
    )

    settings.update({
        'pyramid_oereb': parse(cfg_file, cfg_section)
    })

    config.include('pyramid_oereb.routes')
