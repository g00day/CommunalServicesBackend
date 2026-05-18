from urllib.parse import urlsplit, urlunsplit

from jinja2 import pass_context
from sqladmin import Admin as SQLAdmin
from sqladmin.helpers import get_object_identifier
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response


class RelativeUrlAdmin(SQLAdmin):
    """SQLAdmin variant that uses relative /admin URLs behind reverse proxies."""

    @staticmethod
    def _relative_url(request: Request, name: str, **path_params) -> str:
        absolute_url = str(request.url_for(name, **path_params))
        parsed = urlsplit(absolute_url)
        return urlunsplit(("", "", parsed.path, parsed.query, parsed.fragment))

    def init_templating_engine(self):
        templates = super().init_templating_engine()

        @pass_context
        def url_for(context: dict, name: str, /, **path_params):
            request: Request = context["request"]
            return self._relative_url(request, name, **path_params)

        templates.env.globals["url_for"] = url_for
        return templates

    async def login(self, request: Request) -> Response:
        if self.authentication_backend is None:
            raise RuntimeError("Authentication backend not configured.")

        context = {}
        if request.method == "GET":
            return await self.templates.TemplateResponse(request, "sqladmin/login.html")

        ok = await self.authentication_backend.login(request)
        if not ok:
            context["error"] = "Invalid credentials."
            return await self.templates.TemplateResponse(
                request, "sqladmin/login.html", context, status_code=400
            )

        return RedirectResponse(self._relative_url(request, "admin:index"), status_code=302)

    async def logout(self, request: Request) -> Response:
        if self.authentication_backend is None:
            raise RuntimeError("Authentication backend not configured.")

        response = await self.authentication_backend.logout(request)
        if isinstance(response, Response):
            return response

        return RedirectResponse(self._relative_url(request, "admin:index"), status_code=302)

    def get_save_redirect_url(self, request: Request, form, model_view, obj):
        identity = request.path_params["identity"]
        identifier = get_object_identifier(obj)

        if form.get("save") == "Save":
            return self._relative_url(request, "admin:list", identity=identity)

        if form.get("save") == "Save and continue editing" or (
            form.get("save") == "Save as new" and model_view.save_as_continue
        ):
            return self._relative_url(
                request, "admin:edit", identity=identity, pk=identifier
            )

        return self._relative_url(request, "admin:create", identity=identity)
