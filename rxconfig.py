import reflex as rx
from reflex_base.plugins.sitemap import SitemapPlugin
from reflex_components_radix.plugin import RadixThemesPlugin

config = rx.Config(
    app_name="dashboard",
    plugins=[
        SitemapPlugin(),
        RadixThemesPlugin(
            theme=rx.theme(appearance="light", accent_color="indigo", radius="medium")
        ),
    ],
)
