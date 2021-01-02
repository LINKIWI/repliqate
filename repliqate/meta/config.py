import yaml

# Map of node expressions to reasonably sane default values for some configuration directives.
# Required configuration directives are deliberately omitted.
CONFIG_DEFAULTS = {
    # If omitted, don't report metrics
    'statsd_addr': None,
    # If omitted, retain state in-memory
    'redis_addr': None,
    # If omitted, fetch all fields
    'replication.sql_source.fields': [],
    # If omitted, fetch all rows past the last committed offset
    'replication.sql_source.limit': None,
    # If omitted, assume Kafka brokers on the local machine listening on the default port
    'replication.kafka_target.brokers': ['localhost:9092'],
}


class InvalidConfigException(Exception):
    """
    Raised when the supplied configuration is invalid.
    """
    pass


class InvalidConfigDirectiveException(Exception):
    """
    Raised when attempting to access a property that does not exist.
    """
    pass


class Config(object):
    """
    Object describing a configuration file.
    """

    def __init__(self, path):
        """
        Initialize and validate a configuration file.

        :param path: Path to the YAML configuration.
        """
        self.config = yaml.load(open(path), Loader=yaml.FullLoader)

        self._validate()

    def __repr__(self):
        """
        Get a representation of this configuration.

        :return: Representation of the underlying YAML.
        """
        return repr(self.config)

    def get(self, node):
        """
        Read the value of a configuration directive by its node expression. Nodes are described
        hierarchically, delimited with a dot.

        :param node: Node expression for the directive.
        :return: Value at the specified node (may be a dict, list, or literal primitive) if it
                 exists. Returns a default value if specified; otherwise raises an exception.
        """
        def lookup(config, path):
            if not path:
                return config

            current = path[0]
            rest = path[1:]

            if current not in config:
                raise InvalidConfigDirectiveException('Node `{}` does not exist.'.format(current))

            return lookup(config[current], rest)

        try:
            return lookup(self.config['repliqate'], node.split('.'))
        except InvalidConfigDirectiveException:
            if node not in CONFIG_DEFAULTS:
                raise

            return CONFIG_DEFAULTS[node]

    def _validate(self):
        """
        Validate the supplied configuration. Raises an exception if it is found to be invalid;
        noops otherwise.
        """
        if 'repliqate' not in self.config:
            raise InvalidConfigException('Top-level `repliqate` node missing.')

        required_nodes = [
            'name',
            'replication.poll_interval_sec',
            'replication.sql_source.uri',
            'replication.sql_source.table',
            'replication.sql_source.primary_key',
            'replication.kafka_target.topic',
        ]

        for node in required_nodes:
            try:
                self.get(node)
            except InvalidConfigDirectiveException:
                raise InvalidConfigException('Required node `{}` missing.'.format(node))
