import threading

import redis
from redis.exceptions import ConnectionError
from redis.exceptions import TimeoutError


class CacheException(Exception):
    """
    Application-level exception raised by the client for invalid parameters.
    """
    pass


class MemoryCache(object):
    """
    MemoryCache is a simple, thread-safe in-memory key-value cache.
    """

    def __init__(self):
        """
        Create a MemoryCache with the default in-memory storage backend.
        """
        self.lock = threading.Lock()
        self.store = {}

    def get(self, key):
        """
        Retrieve a key's value.

        :param key: Raw key.
        :return: Associated value, if it exists and is prior to expiry.
        """
        with self.lock:
            try:
                return self.store[key]
            except KeyError:
                return None

    def set(self, key, value):
        """
        Set a key-value pair.

        :param key: Raw key.
        :param value: Associated value.
        """
        with self.lock:
            self.store[key] = str(value)

    def delete(self, key):
        """
        Delete a key, if it exists.

        :param key: Raw key.
        """
        with self.lock:
            if key in self.store:
                del self.store[key]


class RedisProxyClient(object):
    """
    Intermediary proxy client in front of Redis that gracefully falls back to an in-memory cache if
    Redis fails or is otherwise unavailable, to provide additional resiliency.
    """

    def __init__(self, addr, contention_resolution):
        """
        Create a RedisProxyClient.

        :param addr: Address to the Redis cluster.
        :param contention_resolution: Function expressing how to resolve conflicts on read
                                      inconsistencies between the primary and failover clients.
        """
        ip, port = addr.split(':')

        self.contention_resolution = contention_resolution or (lambda primary, secondary: primary)
        self.memory = MemoryCache()
        self.redis = redis.Redis(
            host=ip,
            port=port,
        )

    def get(self, key):
        """
        Get the value for a key, prioritizing Redis if available.

        :param key: Raw key.
        :return: Associated value.
        """
        try:
            redis_val = self.redis.get(key)
            mem_val = self.memory.get(key)

            if redis_val != mem_val:
                resolved_val = self.contention_resolution(redis_val, mem_val)
                self.set(key, resolved_val)
                return resolved_val

            return redis_val
        except (ConnectionError, TimeoutError):
            return self.memory.get(key)

    def set(self, key, value):
        """
        Set the value for a key. Dark writes to the backup in-memory store are always performed
        to synchronize the state of the in-memory store with Redis, so that read failovers do not
        sacrifice the consistency of the underlying data.

        :param key: Raw key.
        :param value: Associated value.
        """
        try:
            return self.redis.set(key, value)
        except (ConnectionError, TimeoutError):
            pass
        finally:
            return self.memory.set(key, value)

    def delete(self, key):
        """
        Invalidate a cache entry. Like the other write operation set(), dark writes are always
        performed to keep the in-memory cache consistent with Redis in the event of a failover.

        :param key: Raw key.
        """
        try:
            return self.redis.delete(key)
        except (ConnectionError, TimeoutError):
            pass
        finally:
            return self.memory.delete(key)


class KeyValueStoreClient(object):
    """
    Caching abstractions on top of a key value storage system.
    """

    def __init__(self, addr, prefix, contention_resolution=None):
        """
        Create a key value store client with a Redis backend.

        :param addr: Address of the Redis cluster.
        :param prefix: String prefix for all inserted cache keys.
        :param contention_resolution: Function expressing how to resolve conflicts on read
                                      inconsistencies between the primary and failover clients.
        """
        self.prefix = prefix

        if addr:
            self.backend = RedisProxyClient(addr, contention_resolution)
        else:
            self.backend = MemoryCache()

    def closure(self, namespace, key, tags={}):
        """
        Factory for a key value read/write client for a particular key.

        :param namespace: Namespace of the key.
        :param key: The key itself.
        :param tags: Optional dictionary of tags to qualify the key.
        :return: A client with get and set methods within this client's closure.
        """
        def set_proxy(value):
            return self.set(namespace, key, tags, value)

        def get_proxy():
            return self.get(namespace, key, tags)

        def delete_proxy():
            return self.delete(namespace, key, tags)

        return KeyValueStoreClosure(set_proxy, get_proxy, delete_proxy)

    def get(self, namespace, key, tags={}):
        """
        Get a value.

        :param namespace: Namespace of the key.
        :param key: The key itself.
        :param tags: Optional dictionary of tags to qualify the key.
        :return: The cached value, if available; None otherwise.
        """
        return self.backend.get(
            key=self._format_key(namespace, key, tags),
        )

    def set(self, namespace, key, tags, value):
        """
        Set a value. This operation treats new entries and updates to existing entries
        identically.

        :param namespace: Namespace of the key.
        :param key:The key itself.
        :param tags: Optional dictionary of tags to qualify the key.
        :param value: Value to set.
        """
        self.backend.set(
            key=self._format_key(namespace, key, tags),
            value=value,
        )

    def delete(self, namespace, key, tags):
        """
        Delete an entry.

        :param namespace: Namespace of the key.
        :param key: The key itself.
        :param tags: Optional dictionary of tags to qualify the key.
        """
        self.backend.delete(
            key=self._format_key(namespace, key, tags),
        )

    def _format_key(self, namespace, key, tags, delimiter=':'):
        """
        Serialize a (namespace, key, tags) triple to a plain-text string used as the raw key in the
        key-value storage backend.

        :param namespace: Namespace of the key.
        :param key:The key itself.
        :param tags: Optional dictionary of tags to qualify the key.
        :param delimiter: String delimiter used for separating the key qualifiers during
                          serialization. A colon is conventional for Redis keys.
        :return: Formatted key string for insertion into the database.
        """
        def format_tag_kv_pair(tag_key, tag_value):
            if {'=', '&'}.intersection('{}{}'.format(tag_key, tag_value)):
                raise CacheException('Cache tag key or value contains illegal characters')

            return '{}={}'.format(tag_key, tag_value)

        serialized_tags = '&'.join(
            format_tag_kv_pair(tag_key, tag_value)
            for tag_key, tag_value in tags.items()
        )

        return '{prefix}{delimiter}{namespace}{delimiter}{key}{delimiter}{tags}'.format(
            delimiter=delimiter,
            prefix=self.prefix,
            namespace=namespace,
            key=key,
            tags=serialized_tags,
        )


class KeyValueStoreClosure:
    """
    Simple object container that proxies read/write methods within the closure of the cache client.
    This is merely a usage abstraction to allow clients to call read and write methods without
    repeating the same key qualification arguments.
    """

    def __init__(self, set_proxy, get_proxy, delete_proxy):
        """
        Create a CacheKeyRWClient.

        :param set_proxy: Function that proxies the host set() method.
        :param get_proxy: Function that proxies the host get() method.
        :param delete_proxy: Function that proxies the host delete() method.
        """
        self.set = set_proxy
        self.get = get_proxy
        self.delete = delete_proxy
