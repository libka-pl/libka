"""
Tiny module to handle `LibkaTheAddon()` singleton instance.
"""

from .addon import LibkaTheAddon

#: Libka addon
libka = LibkaTheAddon()

#: Direct access to media.
media = libka.media
