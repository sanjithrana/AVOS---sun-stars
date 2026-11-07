import pytest

from agentic_core.models.image.chain import ImageProviderChain
from agentic_core.models.image.cloudflare_provider import CloudflareImageProvider
from agentic_core.models.image.factory import get_image_provider
from agentic_core.models.image.local_provider import LocalImageProvider
from agentic_core.models.image.pollinations_provider import PollinationsProvider
from agentic_core.models.image.replicate_provider import ReplicateImageProvider
from agentic_core.models.image.stability_provider import StabilityImageProvider
from agentic_core.models.video.factory import get_video_provider
from agentic_core.models.video.local_provider import LocalVideoProvider


@pytest.fixture(autouse=True)
def _clear_provider_env(monkeypatch):
    for var in (
        "IMAGE_PROVIDER",
        "POLLINATIONS_MODEL",
        "IMAGE_SERVICE_URL",
        "CLOUDFLARE_ACCOUNT_ID",
        "CLOUDFLARE_API_TOKEN",
        "CLOUDFLARE_IMAGE_MODEL",
        "CLOUDFLARE_DAILY_IMAGE_LIMIT",
        "REPLICATE_API_TOKEN",
        "REPLICATE_IMAGE_MODEL",
        "REPLICATE_IMAGE_COST_USD",
        "STABILITY_API_KEY",
        "STABILITY_IMAGE_COST_USD",
        "IMAGE_PAID_DAILY_SPEND_CAP_USD",
        "VIDEO_PROVIDER",
        "VIDEO_SERVICE_URL",
    ):
        monkeypatch.delenv(var, raising=False)


# -- image ---------------------------------------------------------------


def test_image_no_choice_returns_none_to_keep_mock_thumbnails():
    assert get_image_provider(None) is None


def test_image_explicit_mock_returns_none():
    assert get_image_provider("mock") is None


def test_image_env_default_does_not_auto_run_without_being_set():
    # Sanity check: with nothing set at all (fixture cleared it), still None.
    assert get_image_provider(None) is None


def test_image_pollinations_needs_no_credential():
    provider = get_image_provider("pollinations")
    assert isinstance(provider, PollinationsProvider)
    assert provider.model == "flux"


def test_image_pollinations_reads_model_from_env(monkeypatch):
    monkeypatch.setenv("POLLINATIONS_MODEL", "turbo")
    provider = get_image_provider("pollinations")
    assert provider.model == "turbo"


def test_image_local_without_service_url_raises():
    with pytest.raises(ValueError, match="IMAGE_SERVICE_URL"):
        get_image_provider("local")


def test_image_local_with_service_url_returns_local_provider(monkeypatch):
    monkeypatch.setenv("IMAGE_SERVICE_URL", "http://localhost:7860")
    provider = get_image_provider("local")
    assert isinstance(provider, LocalImageProvider)
    assert provider.base_url == "http://localhost:7860"


def test_image_unknown_choice_raises():
    with pytest.raises(ValueError, match="Unknown image provider"):
        get_image_provider("not-a-real-provider")


def test_image_env_default_used_when_no_explicit_choice(monkeypatch):
    monkeypatch.setenv("IMAGE_PROVIDER", "pollinations")
    provider = get_image_provider(None)
    assert isinstance(provider, PollinationsProvider)


def test_image_explicit_choice_overrides_env_default(monkeypatch):
    monkeypatch.setenv("IMAGE_PROVIDER", "pollinations")
    assert get_image_provider("mock") is None


def test_image_cloudflare_without_credentials_raises():
    with pytest.raises(ValueError, match="CLOUDFLARE_ACCOUNT_ID"):
        get_image_provider("cloudflare")


def test_image_cloudflare_with_credentials_returns_cloudflare_provider(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct123")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "token456")
    provider = get_image_provider("cloudflare")
    assert isinstance(provider, CloudflareImageProvider)
    assert provider.account_id == "acct123"
    assert provider.api_token == "token456"
    assert provider.model == "@cf/black-forest-labs/flux-1-schnell"


def test_image_chain_always_includes_pollinations_with_nothing_else_configured():
    provider = get_image_provider("chain")
    assert isinstance(provider, ImageProviderChain)
    assert len(provider.members) == 1
    assert isinstance(provider.members[0].provider, PollinationsProvider)
    assert provider.members[0].daily_request_limit is None  # no daily cap tracked
    assert provider.members[0].is_paid is False


def test_image_chain_adds_cloudflare_when_configured(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct123")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "token456")
    provider = get_image_provider("chain")
    assert isinstance(provider, ImageProviderChain)
    names = [m.provider.name for m in provider.members]
    assert names == ["pollinations", "cloudflare"]
    assert provider.members[1].daily_request_limit == 1500  # default


def test_image_chain_respects_custom_cloudflare_daily_limit(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct123")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "token456")
    monkeypatch.setenv("CLOUDFLARE_DAILY_IMAGE_LIMIT", "42")
    provider = get_image_provider("chain")
    assert provider.members[1].daily_request_limit == 42


def test_image_chain_adds_local_when_configured(monkeypatch):
    monkeypatch.setenv("IMAGE_SERVICE_URL", "http://localhost:7860")
    provider = get_image_provider("chain")
    names = [m.provider.name for m in provider.members]
    assert names == ["pollinations", "local"]
    assert provider.members[1].daily_request_limit is None  # local has no daily cap


def test_image_chain_includes_all_free_providers_when_all_configured(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct123")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "token456")
    monkeypatch.setenv("IMAGE_SERVICE_URL", "http://localhost:7860")
    provider = get_image_provider("chain")
    names = [m.provider.name for m in provider.members]
    assert names == ["pollinations", "cloudflare", "local"]


def test_image_replicate_without_token_raises():
    with pytest.raises(ValueError, match="REPLICATE_API_TOKEN"):
        get_image_provider("replicate")


def test_image_replicate_with_token_returns_replicate_provider(monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "r8_test")
    provider = get_image_provider("replicate")
    assert isinstance(provider, ReplicateImageProvider)
    assert provider.model == "black-forest-labs/flux-schnell"


def test_image_stability_without_key_raises():
    with pytest.raises(ValueError, match="STABILITY_API_KEY"):
        get_image_provider("stability")


def test_image_stability_with_key_returns_stability_provider(monkeypatch):
    monkeypatch.setenv("STABILITY_API_KEY", "sk-test")
    provider = get_image_provider("stability")
    assert isinstance(provider, StabilityImageProvider)


def test_image_chain_never_adds_paid_providers_without_their_keys():
    provider = get_image_provider("chain")
    names = [m.provider.name for m in provider.members]
    assert "replicate" not in names
    assert "stability" not in names


def test_image_chain_adds_paid_providers_last_when_configured(monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "r8_test")
    monkeypatch.setenv("STABILITY_API_KEY", "sk-test")
    provider = get_image_provider("chain")
    names = [m.provider.name for m in provider.members]
    assert names == ["pollinations", "replicate", "stability"]
    assert provider.members[1].is_paid is True
    assert provider.members[2].is_paid is True


def test_image_chain_paid_members_share_the_default_spend_cap(monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "r8_test")
    monkeypatch.setenv("STABILITY_API_KEY", "sk-test")
    provider = get_image_provider("chain")
    replicate_member = next(m for m in provider.members if m.provider.name == "replicate")
    stability_member = next(m for m in provider.members if m.provider.name == "stability")
    assert replicate_member.daily_spend_cap_usd == 0.50  # default
    assert stability_member.daily_spend_cap_usd == 0.50  # same cap, shared


def test_image_chain_respects_custom_spend_cap_and_costs(monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "r8_test")
    monkeypatch.setenv("IMAGE_PAID_DAILY_SPEND_CAP_USD", "2.5")
    monkeypatch.setenv("REPLICATE_IMAGE_COST_USD", "0.01")
    provider = get_image_provider("chain")
    replicate_member = next(m for m in provider.members if m.provider.name == "replicate")
    assert replicate_member.daily_spend_cap_usd == 2.5
    assert replicate_member.cost_per_call_usd == 0.01


# -- video -----------------------------------------------------------------


def test_video_no_choice_returns_none():
    assert get_video_provider(None) is None


def test_video_explicit_mock_returns_none():
    assert get_video_provider("mock") is None


def test_video_local_without_service_url_raises():
    with pytest.raises(ValueError, match="VIDEO_SERVICE_URL"):
        get_video_provider("local")


def test_video_local_with_service_url_returns_local_provider(monkeypatch):
    monkeypatch.setenv("VIDEO_SERVICE_URL", "http://localhost:9000")
    provider = get_video_provider("local")
    assert isinstance(provider, LocalVideoProvider)
    assert provider.base_url == "http://localhost:9000"


def test_video_unknown_choice_raises():
    with pytest.raises(ValueError, match="Unknown video provider"):
        get_video_provider("not-a-real-provider")


def test_video_env_default_used_when_no_explicit_choice(monkeypatch):
    monkeypatch.setenv("VIDEO_PROVIDER", "local")
    monkeypatch.setenv("VIDEO_SERVICE_URL", "http://localhost:9000")
    provider = get_video_provider(None)
    assert isinstance(provider, LocalVideoProvider)
