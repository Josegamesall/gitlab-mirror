#    Friendly Telegram (telegram userbot)
#    Copyright (C) 2018-2019 The Authors

#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.

#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

from aiohttp import web
import aiohttp_jinja2
from jinja2.runtime import Undefined
import functools

from .. import main, security


class Web:
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app.router.add_get("/settings", self.settings)
        self.app.router.add_put("/setSetting", self.set_settings)
        self.app.router.add_patch("/setPermissionSet", self.set_permission_set)

    @aiohttp_jinja2.template("settings.jinja2")
    async def settings(self, request):
        uid = await self.check_user(request)
        if uid is None:
            return web.Response(status=302, headers={"Location": "/"})  # They gotta sign in.
        keys = [(main, "prefixes", ["."]),
                (security, "owner", None),
                (security, "sudo", []),
                (security, "support", [])]
        mask = self.client_data[uid][2].get(security.__name__, "bounding_mask", security.DEFAULT_PERMISSIONS)
        db = self.client_data[uid][2]
        return {"checked": functools.partial(self.is_checked, db), "modules": self.client_data[uid][0].modules,
                **security.BITMAP,
                **{key: self.client_data[uid][2].get(mod, key, default) for mod, key, default in keys}}

    def is_checked(self, db, bit, func):
        if isinstance(func, Undefined):
            ret = db.get(security.__name__, "bounding_mask", security.DEFAULT_PERMISSIONS) & bit
        else:
            ret = db.get(security.__name__, "masks", {}).get(func.__self__.__module__ + "."
                                                             + func.__name__,
                                                             getattr(func, "security",
                                                                     db.get(security.__name__, "default",
                                                                     security.DEFAULT_PERMISSIONS))) & bit
        return "checked" if ret else ""

    async def set_owner(self, request):
        uid = await self.check_user(request)
        if uid is None:
            return web.Response(status=401)
        try:
            self.client_data[uid][2].set(security.__name__, "owner", int(await request.text()))
        except ValueError:
            return web.Response(status=400)
        return web.Response()

    async def set_group(self, request):
        uid = await self.check_user(request)
        if uid is None:
            return web.Response(status=401)
        data = await request.json()
        if data.get("group", None) not in ("sudo", "support"):
            return web.Response(status=400)
        try:
            self.client_data[uid][2].set(security.__name__, data[group],
                                         [int(user) for user in data["users"].split(",")])
        except (KeyError, ValueError),
            return web.Response(status=400)
        return web.Response()

    async def set_permission_set(self, request):
        uid = await self.check_user(request)
        if uid is None:
            return web.Response(status=401)
        data = await request.json()
        try:
            bit = security.BITMAP[data["bit"]]
        except KeyError:
            return web.Response(status=400)
        mod = self.client_data[uid][0].modules[int(data["mid"])]
        func = data["func"]
        if mod and func:
            mask = self.client_data[uid][2].get(security.__name__, "masks", {}).get(mod.__module__ + "." + func, getattr(mod.commands[func], "security", security.DEFAULT_PERMISSIONS))
        else:
            mask = self.client_data[uid][2].get(security.__name__, "bounding_mask", security.DEFAULT_PERMISSIONS)
        try:
            if data["state"]:
                mask |= bit
            else:
                mask &= ~bit
        except KeyError:
            return web.Response(status=400)
        if mod and func:
            masks = self.client_data[uid][2].get(security.__name__, "masks", {})
            masks[mod.__module__ + "." + func] = mask
            self.client_data[uid][2].set(security.__name__, "masks", masks)
        else:
            self.client_data[uid][2].set(security.__name__, "bounding_mask", mask)
        return web.Response()
