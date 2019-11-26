import json
from pathlib import Path
from typing import Dict

from flask.cli import current_app as app, with_appcontext
# noinspection PyPackageRequirements
from click import command, option, echo, confirm, style as click_style, Path as ClickPath
# noinspection PyPackageRequirements
import ulid
# noinspection PyPackageRequirements
from airtable import Airtable as _Airtable

from bas_web_map_inventory.components import Server, Servers, Namespaces, Namespace, Repositories, Repository, Styles, \
    Style, Layers, Layer, LayerGroup, LayerGroups
from bas_web_map_inventory.components.geoserver import GeoServer
from bas_web_map_inventory.components.airtable import ServersAirtable, NamespacesAirtable, RepositoriesAirtable, \
    StylesAirtable, LayersAirtable, LayerGroupsAirtable


# Utils

def _load_data() -> None:
    app.logger.info('Loading data...')

    with open(Path('resources/data.json'), 'r') as data_file:
        _data = data_file.read()
    data = json.loads(_data)

    servers = Servers()
    for server in data['servers']:
        server = Server(
            server_id=server['id'],
            label=server['label'],
            hostname=server['hostname'],
            server_type=server['type'],
            version=server['version']
        )
        servers[server.id] = server

    namespaces = Namespaces()
    for namespace in data['namespaces']:
        namespace = Namespace(
            namespace_id=namespace['id'],
            label=namespace['label'],
            title=namespace['title'],
            namespace=namespace['namespace'],
            isolated=namespace['isolated'],
            server=servers[namespace['relationships']['servers']]
        )
        namespaces[namespace.id] = namespace

    repositories = Repositories()
    for repository in data['repositories']:
        repository = Repository(
            repository_id=repository['id'],
            label=repository['label'],
            title=repository['title'],
            repository_type=repository['type'],
            hostname=repository['hostname'],
            database=repository['database'],
            schema=repository['schema'],
            namespace=namespaces[repository['relationships']['namespaces']]
        )
        repositories[repository.id] = repository

    styles = Styles()
    for style in data['styles']:
        _namespace = None
        if style['relationships']['namespaces'] is not None:
            _namespace = namespaces[style['relationships']['namespaces']]
        style = Style(
            style_id=style['id'],
            label=style['label'],
            title=style['title'],
            style_type=style['type'],
            namespace=_namespace
        )
        styles[style.id] = style

    layers = Layers()
    for layer in data['layers']:
        _styles = []
        for style_id in layer['relationships']['styles']:
            _styles.append(styles[style_id])
        layer = Layer(
            layer_id=layer['id'],
            label=layer['label'],
            title=layer['title'],
            layer_type=layer['type'],
            geometry_type=layer['geometry'],
            services=layer['services'],
            table_view=layer['table_view'],
            namespace=namespaces[layer['relationships']['namespaces']],
            repository=repositories[layer['relationships']['repositories']],
            styles=_styles
        )
        layers[layer.id] = layer

    layer_groups = LayerGroups()
    for layer_group in data['layer-groups']:
        _namespace = None
        if layer_group['relationships']['namespaces'] is not None:
            _namespace = namespaces[layer_group['relationships']['namespaces']]
        _layers = []
        for layer_id in layer_group['relationships']['layers']:
            _layers.append(layers[layer_id])
        _styles = []
        for style_id in layer_group['relationships']['styles']:
            _styles.append(styles[style_id])
        layer_group = LayerGroup(
            layer_group_id=layer_group['id'],
            label=layer_group['label'],
            title=layer_group['title'],
            services=layer_group['services'],
            namespace=_namespace,
            layers=_layers,
            styles=_styles
        )
        layer_groups[layer_group.id] = layer_group

    app.config['data'] = {
        'servers': servers,
        'namespaces': namespaces,
        'repositories': repositories,
        'styles': styles,
        'layers': layers,
        'layer_groups': layer_groups
    }


def _setup_airtable() -> None:
    app.logger.info('Loading Airtable data...')

    _servers_airtable = _Airtable(
        base_key=app.config['AIRTABLE_BASE_ID'],
        api_key=app.config['AIRTABLE_API_KEY'],
        table_name='Servers'
    )
    servers_airtable = ServersAirtable(
        airtable=_servers_airtable,
        servers=app.config['data']['servers']
    )

    _namespaces_airtable = _Airtable(
        base_key=app.config['AIRTABLE_BASE_ID'],
        api_key=app.config['AIRTABLE_API_KEY'],
        table_name='Workspaces'
    )
    namespaces_airtable = NamespacesAirtable(
        airtable=_namespaces_airtable,
        namespaces=app.config['data']['namespaces'],
        servers_airtable=servers_airtable
    )

    _repositories_airtable = _Airtable(
        base_key=app.config['AIRTABLE_BASE_ID'],
        api_key=app.config['AIRTABLE_API_KEY'],
        table_name='Stores'
    )
    repositories_airtable = RepositoriesAirtable(
        airtable=_repositories_airtable,
        repositories=app.config['data']['repositories'],
        namespaces_airtable=namespaces_airtable
    )

    _styles_airtable = _Airtable(
        base_key=app.config['AIRTABLE_BASE_ID'],
        api_key=app.config['AIRTABLE_API_KEY'],
        table_name='Styles'
    )
    styles_airtable = StylesAirtable(
        airtable=_styles_airtable,
        styles=app.config['data']['styles'],
        namespaces_airtable=namespaces_airtable
    )

    _layers_airtable = _Airtable(
        base_key=app.config['AIRTABLE_BASE_ID'],
        api_key=app.config['AIRTABLE_API_KEY'],
        table_name='Layers'
    )
    layers_airtable = LayersAirtable(
        airtable=_layers_airtable,
        layers=app.config['data']['layers'],
        namespaces_airtable=namespaces_airtable,
        repositories_airtable=repositories_airtable,
        styles_airtable=styles_airtable
    )

    _layer_groups_airtable = _Airtable(
        base_key=app.config['AIRTABLE_BASE_ID'],
        api_key=app.config['AIRTABLE_API_KEY'],
        table_name='Layer Groups'
    )
    layer_groups_airtable = LayerGroupsAirtable(
        airtable=_layer_groups_airtable,
        layer_groups=app.config['data']['layer_groups'],
        namespaces_airtable=namespaces_airtable,
        styles_airtable=styles_airtable,
        layers_airtable=layers_airtable
    )

    app.config['airtable'] = {
        'servers': servers_airtable,
        'namespaces': namespaces_airtable,
        'repositories': repositories_airtable,
        'styles': styles_airtable,
        'layers': layers_airtable,
        'layer_groups': layer_groups_airtable
    }


def _process_component_airtable_status(global_status: Dict[str, int], component_type: str):
    echo(f"Getting status for {click_style(component_type.capitalize(), fg='cyan')}:")
    _status = app.config['airtable'][component_type].status()
    global_status['current'] += len(_status['current'])
    global_status['outdated'] += len(_status['outdated'])
    global_status['missing'] += len(_status['missing'])
    global_status['orphaned'] += len(_status['orphaned'])
    echo(f"* current: {click_style(str(len(_status['current'])), fg='blue')}")
    echo(f"* outdated: {click_style(str(len(_status['outdated'])), fg='blue')}")
    echo(f"* missing: {click_style(str(len(_status['missing'])), fg='blue')}")
    echo(f"* orphaned: {click_style(str(len(_status['orphaned'])), fg='blue')}")
    echo(_status)


# Commands


@command()
@option(
    '-s',
    '--data-sources-file-path',
    default='resources/sources.json',
    show_default=True,
    type=ClickPath(exists=True)
)
@option(
    '-d',
    '--data-output-file-path',
    default='resources/data.json',
    show_default=True,
    type=ClickPath()
)
@with_appcontext
def fetch(data_sources_file_path: str, data_output_file_path):
    """Fetch data from data sources into a data file"""
    app.config['data'] = {}

    echo(f"loading sources from {click_style(data_sources_file_path, fg='blue')}")
    echo("")
    with open(Path(data_sources_file_path), 'r') as data_sources_file:
        data_sources_data = data_sources_file.read()
    data_sources = json.loads(data_sources_data)

    echo(f"Fetching {click_style('Servers', fg='cyan')}:")
    servers = Servers()
    for server_config in data_sources['servers']:
        if server_config['type'] == 'geoserver':
            server = GeoServer(
                server_id=server_config['id'],
                label=server_config['label'],
                hostname=server_config['hostname'],
                port=server_config['port'],
                api_path=server_config['api-path'],
                wfs_path=server_config['wfs-path'],
                wms_path=server_config['wms-path'],
                username=server_config['username'],
                password=server_config['password']
            )
            servers[server.id] = server
    app.config['data']['servers'] = servers
    echo(f"* fetched {click_style(str(len(servers)), fg='blue')} servers (total)")

    server_namespaces = {}
    for server in servers.values():
        server_namespaces[server.id] = []
        if isinstance(server, GeoServer):
            for namespace in server.get_namespaces():
                server_namespaces[server.id].append(server.get_namespace(namespace_reference=namespace))

    namespaces = Namespaces()
    for server_id, _namespaces in server_namespaces.items():
        echo(f"Fetching {click_style('Namespaces', fg='cyan')} in "
             f"{click_style(servers[server_id].label, fg='magenta')}:")
        for namespace in _namespaces:
            namespace = Namespace(
                namespace_id=ulid.new().str,
                label=namespace['label'],
                title=namespace['title'],
                namespace=namespace['namespace'],
                isolated=False,
                server=servers[server_id]
            )
            namespaces[namespace.id] = namespace
        echo(f"* fetched {click_style(str(len(_namespaces)), fg='blue')} namespaces for "
             f"{click_style(servers[server_id].label, fg='magenta')}")
    app.config['data']['namespaces'] = namespaces
    echo(f"* fetched {click_style(str(len(namespaces)), fg='blue')} namespaces (total)")

    repositories = Repositories()
    for server in servers.values():
        _repositories_server_count = 0
        echo(f"Fetching {click_style('Repositories', fg='cyan')} in {click_style(server.label, fg='magenta')}:")
        for _repository in server.get_repositories():
            _repositories_server_count += 1
            _repository = server.get_repository(
                repository_reference=_repository[0], namespace_reference=_repository[1])
            _repository['repository_id'] = ulid.new().str
            _repository['namespace'] = namespaces.get_by_label(label=_repository['namespace_label'])
            del(_repository['namespace_label'])
            repository = Repository(**_repository)
            repositories[repository.id] = repository
        echo(f"* fetched {click_style(str(_repositories_server_count), fg='blue')} repositories for "
             f"{click_style(server.label, fg='magenta')}")
    app.config['data']['repositories'] = repositories
    echo(f"* fetched {click_style(str(len(repositories)), fg='blue')} repositories (total)")

    styles = Styles()
    for server in servers.values():
        _styles_server_count = 0
        echo(f"Fetching {click_style('Styles', fg='cyan')} in {click_style(server.label, fg='magenta')}:")
        for _style in server.get_styles():
            _styles_server_count += 1
            _style = server.get_style(style_reference=_style[0], namespace_reference=_style[1])
            _style['style_id'] = ulid.new().str
            if 'namespace_label' in _style:
                _style['namespace'] = namespaces.get_by_label(label=_style['namespace_label'])
                del(_style['namespace_label'])
            style = Style(**_style)
            styles[style.id] = style
        echo(f"* fetched {click_style(str(_styles_server_count), fg='blue')} styles for "
             f"{click_style(server.label, fg='magenta')}")
    app.config['data']['styles'] = styles
    echo(f"* fetched {click_style(str(len(styles)), fg='blue')} styles (total)")

    layers = Layers()
    for server in servers.values():
        _layers_server_count = 0
        echo(f"Fetching {click_style('Layers', fg='cyan')} in {click_style(server.label, fg='magenta')}:")
        for _layer in server.get_layers():
            _layers_server_count += 1
            _layer = server.get_layer(layer_reference=_layer)
            _layer['layer_id'] = ulid.new().str
            _layer['namespace'] = namespaces.get_by_label(label=_layer['namespace_label'])
            _layer['repository'] = repositories.get_by_label(label=_layer['repository_label'])
            _layer['styles'] = []
            for _style_label in _layer['style_labels']:
                _layer['styles'].append(styles.get_by_label(label=_style_label[0], namespace_label=_style_label[1]))
            del _layer['namespace_label']
            del _layer['repository_label']
            del _layer['style_labels']
            layer = Layer(**_layer)
            layers[layer.id] = layer
        echo(f"* fetched {click_style(str(_layers_server_count), fg='blue')} layers for "
             f"{click_style(server.label, fg='magenta')}")
    app.config['data']['layers'] = layers
    echo(f"* fetched {click_style(str(len(layers)), fg='blue')} layers (total)")

    layer_groups = Layers()
    for server in servers.values():
        _layer_groups_server_count = 0
        echo(f"Fetching {click_style('Layer Groups', fg='cyan')} in {click_style(server.label, fg='magenta')}:")
        for _layer_group in server.get_layer_groups():
            _layer_groups_server_count += 1
            _layer_group = server.get_layer_group(
                layer_group_reference=_layer_group[0],
                namespace_reference=_layer_group[1]
            )
            _layer_group['layer_group_id'] = ulid.new().str
            _layer_group['namespace'] = namespaces.get_by_label(label=_layer_group['namespace_label'])
            _layer_group['layers'] = []
            for _layer_label in _layer_group['layer_labels']:
                _layer_group['layers'].append(layers.get_by_label(
                    label=_layer_label[0], namespace_label=_layer_label[1]))
            _layer_group['styles'] = []
            for _style_label in _layer_group['style_labels']:
                _layer_group['styles'].append(styles.get_by_label(
                    label=_style_label[0], namespace_label=_style_label[1]))
            del _layer_group['namespace_label']
            del _layer_group['layer_labels']
            del _layer_group['style_labels']
            layer_group = LayerGroup(**_layer_group)
            layer_groups[layer_group.id] = layer_group
        echo(f"* fetched {click_style(str(_layer_groups_server_count), fg='blue')} layer groups for "
             f"{click_style(server.label, fg='magenta')}")
    app.config['data']['layer_groups'] = layer_groups
    echo(f"* fetched {click_style(str(len(layer_groups)), fg='blue')} layer groups (total)")

    echo(f"")
    echo(f"Saving fetched data to {click_style(data_output_file_path, fg='blue')}")
    _data = {
        'servers': servers.to_list(),
        'namespaces': namespaces.to_list(),
        'repositories': repositories.to_list(),
        'styles': styles.to_list(),
        'layers': layers.to_list(),
        'layer-groups': layer_groups.to_list()
    }
    with open(Path(data_output_file_path), 'w') as data_file:
        json.dump(_data, data_file, indent=4)
    echo(click_style('Fetch complete', fg='green'))


@command()
@with_appcontext
def status():
    """Get status of all components in Airtable."""
    if 'data' not in app.config:
        _load_data()
    if 'airtable' not in app.config:
        _setup_airtable()

    _global_status = {
        'current': 0,
        'outdated': 0,
        'missing': 0,
        'orphaned': 0
    }

    _process_component_airtable_status(global_status=_global_status, component_type='servers')
    _process_component_airtable_status(global_status=_global_status, component_type='namespaces')
    _process_component_airtable_status(global_status=_global_status, component_type='repositories')
    _process_component_airtable_status(global_status=_global_status, component_type='styles')
    _process_component_airtable_status(global_status=_global_status, component_type='layers')
    _process_component_airtable_status(global_status=_global_status, component_type='layer_groups')

    echo('')
    echo('Status summary:')
    echo(f"* current (total): {click_style(str(_global_status['current']), fg='blue')}")
    echo(f"* outdated (total): {click_style(str(_global_status['outdated']), fg='blue')}")
    echo(f"* missing (total): {click_style(str(_global_status['missing']), fg='blue')}")
    echo(f"* orphaned (total): {click_style(str(_global_status['orphaned']), fg='blue')}")
    echo(click_style('Status complete', fg='green'))


@command()
@with_appcontext
def sync():
    """Sync all components with Airtable."""
    if 'data' not in app.config:
        _load_data()
    if 'airtable' not in app.config:
        _setup_airtable()

    echo(f"Syncing {click_style('Servers', fg='yellow')}:")
    echo(app.config['airtable']['servers'].status())
    app.config['airtable']['servers'].sync()
    echo(app.config['airtable']['servers'].status())
    echo(f"Syncing {click_style('Namespaces (Workspaces)', fg='yellow')}:")
    echo(app.config['airtable']['namespaces'].status())
    app.config['airtable']['namespaces'].sync()
    echo(app.config['airtable']['namespaces'].status())
    echo(f"Syncing {click_style('Repositories (Stores)', fg='yellow')}:")
    echo(app.config['airtable']['repositories'].status())
    app.config['airtable']['repositories'].sync()
    echo(app.config['airtable']['repositories'].status())
    echo(f"Syncing {click_style('Styles', fg='yellow')}:")
    echo(app.config['airtable']['styles'].status())
    app.config['airtable']['styles'].sync()
    echo(app.config['airtable']['styles'].status())
    echo(f"Syncing {click_style('Layers', fg='yellow')}:")
    echo(app.config['airtable']['layers'].status())
    app.config['airtable']['layers'].sync()
    echo(app.config['airtable']['layers'].status())
    echo(f"Syncing {click_style('Layer Groups', fg='yellow')}:")
    echo(app.config['airtable']['layer_groups'].status())
    app.config['airtable']['layer_groups'].sync()
    echo(app.config['airtable']['layer_groups'].status())


@command()
@with_appcontext
def reset():
    """Reset all Airtable data."""
    confirm('Do you really want to continue? All Airtable data will be reset', abort=True)

    if 'data' not in app.config:
        _load_data()
    if 'airtable' not in app.config:
        _setup_airtable()

    echo(f"Resetting {click_style('Servers', fg='red')}:")
    app.config['airtable']['servers'].reset()
    echo(app.config['airtable']['servers_airtable'].status())
    echo(f"Resetting {click_style('Namespaces (Workspaces)', fg='red')}:")
    app.config['airtable']['namespaces'].reset()
    echo(app.config['airtable']['namespaces_airtable'].status())
    echo(f"Resetting {click_style('Repositories (Stores)', fg='red')}:")
    app.config['airtable']['repositories'].reset()
    echo(app.config['airtable']['repositories_airtable'].status())
    echo(f"Resetting {click_style('Styles', fg='red')}:")
    app.config['airtable']['styles'].reset()
    echo(app.config['airtable']['styles_airtable'].status())
    echo(f"Resetting {click_style('Layers', fg='red')}:")
    app.config['airtable']['layers'].reset()
    echo(app.config['airtable']['layers_airtable'].status())
    echo(f"Resetting {click_style('Layer Groups', fg='red')}:")
    app.config['airtable']['layer_groups'].reset()
    echo(app.config['airtable']['layer_groups_airtable'].status())