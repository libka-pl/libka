Usage
-----

To use `requests` wrapper you need to create an instance of `Site`.

```python
site = Site(base='https://docs.python.org/3/library')
txt1 = site.txtget('runpy.html')
txt2 = site.txtget('/3/tutorial/controlflow.html')
txt3 = site.txtget('../tutorial/controlflow.html')
assert txt2 == txt3
resp = site.post('https://www.imdb.com/ap/signin',
                 data={'email': 'my@email.com', 'password': 'abcde'})
if resp.ok:
    ...
```

### Mixin

Simplest way to use `Site` is inherit from it.
All methods from `Site` are available simply by `self`.

```python
from libka import Plugin, Site

class MyPlugin(SiteMixin, Plugin):
    ...
```

There are already prepared classes which join Addon/Plugin and Site benefits:
`libka.SimpleAddon` and `libka.SimplePlugin`.
The same, all methods from `Site` are available simply by `self`.

```python
from libka import SimplePlugin

class MyPlugin(SimplePlugin):

    def __init__(self):
        super.__init__()
        self.base = 'https://extra.site.net/api'

    def home(self):
        """Home folder. Main entry to plugin."""
        # get JSON from https://extra.site.net/api/categories
        data = self.jget('categories')
        with self.directory() as kdir:
            for cat in data:
                kdir.menu(cat['title'], call(self.category, cid=cat['id']))

    def category(cid):
        """Category content."""
        data = self.jget('http://another.site.net/categorty/{cid}',
                         params={'quality': 'FHD'}, on_fail=[])
        with self.directory() as kdir:
            for movie in data:
                kdir.play(movie['title'], call(self.play, cid=movie['id']),
                          info={'duration': movie['duration'])
```


### Instance

Another way to use `Site` is create instance (of more instances).

```python
from libka import Plugin, Site

class MyPlugin(Plugin):

    def __init__(self):
        super.__init__()
        self.site = Site(base='https://extra.site.net/api')
        self.another = Site(base='http://another.site.net')
        self.anysite = Site()
        self.anysite.jpost('https://any.org/token', params={'user': 'me'},
                           json={'token': 'abcde'})

    def home(self):
        """Home folder. Main entry to plugin."""
        # get JSON from https://extra.site.net/api/categories
        data = self.site.jget('categories')
        with self.directory() as kdir:
            for cat in data:
                kdir.menu(cat['title'], call(self.category, cid=cat['id']))

    def category(cid):
        """Category content."""
        # get JSON from http://another.site.net/categorty/<category-id>
        data = self.another.jget('categorty/{cid}',
                                 params={'quality': 'FHD'}, on_fail=[])
        with self.directory() as kdir:
            for movie in data:
                kdir.play(movie['title'], call(self.play, cid=movie['id']),
                          info={'duration': movie['duration'])
```


Details
-------

Base method to work with sites is `Site.request` (it returns `requests.Response`)
but easier use is more specifics:

| Method | `requests.Response` | JSON           | Text           |
| ------ | ------------------- | -------------- | -------------- |
| GET    | `Site.get`          | `Site.jget`    | `Site.txtget`  |
| POST   | `Site.post`         | `Site.jpost`   | `Site.txtpost` |
| PUT    | `Site.put`          | `Site.jput`    | —              |
| PATCH  | `Site.patch`        | `Site.jpatch`  | —              |
| DELETE | `Site.delete`       | `Site.jdelete` | —              |
| HEAD   | `Site.head`         | —              | —              |

HEAD method must be called by `Site.request('HEAD', ...)`.

All `j*` methods return JSON directly. All `txt*` methods return response `text` directly.

Each method has method uses the same arguments like `Site.request` except first (`meth=`),
because HTTP method name is already in specific `Site` method.

Second difference is argument `on_fail=` can contain JSON value for `j*` methods
and string for `txt*` methods.


### URL

Full URL could be used in every method. When `Site` has set `base` property relative URL are also available.


### `on_fail`

Argument `on_fail=` in every request method could be:

- missing, than default `Undefined` is used – exception will be raised on fail
- callable function – `on_fail()` will be called and it result will be returned
- any other value will be returned

`Site.request` and specific methods like `Site.get` need return response object (or similar).  
`j*` methods like `Site.jget` need return decoded JSON.  
`txt*` methods like `Site.txtget` need return `str` text.

```python
from libka import SimplePlugin

class MyPlugin(SimplePlugin):

    def __init__(self):
        super.__init__()
        self.base = 'https://extra.site.net/api'
        # even if fails empty string will be return, then `re` could be called
        text = self.jget('https://good.site.net/', on_fail='')
        for match in re.finditer(r'<a href="(?P<url>.*?)">(?P<title>.*?)</a>', text):
            url, title = match.group('url', 'title')

    def home(self):
        """Home folder. Main entry to plugin."""
        # even if fails empty list [] will be return, then `for in data` could work
        data = self.jget('https://extra.site.net/api/categories', on_fail=[])
        with self.directory() as kdir:
            for cat in data:
                kdir.menu(cat['title'], call(self.category, cid=cat['id']))
```


Concurrent
----------

There is a easy way to get concurrent requests, by `Site.concurrent()` method.


