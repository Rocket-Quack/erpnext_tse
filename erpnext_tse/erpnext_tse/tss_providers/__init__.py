from .fiskaly import FiskalyProvider


def get_tse_provider(settings_doc):
    """Factory fuer den konfigurierten Provider."""
    provider_name = (
        getattr(settings_doc, "tse_provider", None)
        or getattr(settings_doc, "provider", None)
        or "Fiskaly"
    )
    normalized = str(provider_name).strip().lower()

    if normalized in ("fiskaly", "fiskaly (cloud)", "fiskaly_sign_de"):
        return FiskalyProvider(settings_doc)

    # Wenn noetig erweitern mit weiteren Providern
    raise ValueError(f"Unknown TSE provider: {provider_name}")
