

```python
from .libka.menu import Menu, MenuItems

MenuItems.ORDER_KEY = 'title'

class MyPlugin(Plugin):

    MENU = Menu(items=[
        Menu(call='tv'),
        MenuItems(id=1785454, type='directory_series', order={2: 'prog*', 1: 'series', -1: 'teatr*'}),
        Menu(title='Sport', items=[
            Menu(title='Submenu', items=[
                Menu(title='Yet', id=1001),
                Menu(title='Another', id=1002),
            ]),
            Menu(title='Transmission', call='sport'),
            Menu(title='Retransmission', id=48583081),
            Menu(title='Magazine', id=548368),
            Menu(title='Video', id=432801),
        ]),
        Menu(title='Info', id=191888),
        Menu(call='search'),
    ])

    def home(self):
        self.menu()

    def tv(self):
        ...  # called on `call=tv`

    def menu_entry(self, *, entry, kdir, index_path):
        ...  # called when no automation found, ex. `id=N`

    def menu_entry_iter(self, *, entry):
        ...  # called on MenuItems to iterate items from api

    def menu_entry_item(self, *, kdir, entry, item, index_path):
        ...  # called for every item from api

```
