from .fiskaly import FiskalyProvider

def get_tse_provider(settings_doc):
    """Factory für den konfigurierten Provider.

    settings_doc ist dein Single-Doc "TSE Settings".
    """
    provider_name = getattr(settings_doc, "provider", "Fiskaly")

    if provider_name == "Fiskaly":
        return FiskalyProvider(settings_doc)

    # Wenn Notwendig erweitern mit:
    # if provider_name == "XYZ":
    #     return XYZProvider(settings_doc)

    raise ValueError(f"Unknown TSE provider: {provider_name}")