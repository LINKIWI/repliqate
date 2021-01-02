import statsd


class StatsdClient(object):
    """
    Abstractions over statsd metrics emissions.
    """

    def __init__(self, addr, prefix, default_tags={}):
        """
        Create a client instance.

        :param addr: IPv4 address of the statsd server.
        :param prefix: Prefix to attach to all emitted metrics.
        """
        ip, port = addr.split(':')

        self.default_tags = dict(default_tags)
        self.backend = statsd.StatsClient(ip, int(port), prefix=prefix)

    def count(self, metric, value, tags={}):
        """
        Emit a statsd count metric.

        :param metric: Metric name.
        :param value: Delta value.
        :param tags: Optional tags.
        """
        return self.backend.incr(
            stat=self._format_metric(metric, dict(self.default_tags, **tags)),
            count=value,
        )

    def timing(self, metric, duration, tags={}):
        """
        Emit a statsd timing metric.

        :param metric: Metric name.
        :param duration: Duration, in milliseconds.
        :param tags: Optional tags.
        """
        return self.backend.timing(
            stat=self._format_metric(metric, dict(self.default_tags, **tags)),
            delta=duration,
        )

    def gauge(self, metric, value, tags={}):
        """
        Emit a statsd gauge metric.

        :param metric: Metric name.
        :param value: Gauge value.
        :param tags: Optional tags.
        """
        return self.backend.gauge(
            stat=self._format_metric(metric, dict(self.default_tags, **tags)),
            value=value
        )

    @staticmethod
    def _format_metric(metric, tags, tag_delimiter='='):
        """
        Format a metric name to include InfluxDB-style tags.

        :param metric: Metric name.
        :param tags: Dictionary of tags.
        :param tag_delimiter: Tag key-value delimiter; defaults to '=' for InfluxDB-style metrics.
                              Use ':' for Datadog-style metrics.
        :return: Formatted metric name.
        """
        if not tags:
            return metric

        serialized_tags = ','.join(
            '{}{}{}'.format(key, tag_delimiter, value)
            for key, value in tags.items()
        )

        return '{},{}'.format(metric, serialized_tags)
