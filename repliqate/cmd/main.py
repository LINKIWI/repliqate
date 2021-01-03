import argparse
import logging

from repliqate.meta.config import Config
from repliqate.replication.daemon import ReplicationDaemon


def main():
    # Logging configuration
    logging.basicConfig(format='[%(asctime)s] [%(module)s] [%(levelname)s] %(message)s')
    logger = logging.getLogger('repliqate')

    # Command-line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--config',
        default='config.yaml',
        help='path to the config file',
    )
    parser.add_argument(
        '-v',
        '--verbose',
        action='count',
        default=0,
        help='control output logging verbosity: error, warn, info, debug',
    )
    args = parser.parse_args()

    # Start daemon
    config = Config(args.config)
    logger.setLevel(
        [logging.ERROR, logging.WARN, logging.INFO, logging.DEBUG][min(args.verbose, 3)],
    )

    logger.debug('loaded valid config: config={}'.format(config))

    ReplicationDaemon(config).start()


if __name__ == '__main__':
    main()
