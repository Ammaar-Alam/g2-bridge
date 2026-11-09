"""Goggles the bridge knows about: identity codes, picture size, and DUML routes.

Goggles 2 and Integra displayed video over the PC route. The others are
profiles taken from the Virtual Flight app or from device identities, kept
here so the probe and the bridge can try them with explicit consent. A model
with no identity codes can only be selected with assume_model.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class GogglesModel:
    name: str
    codes: tuple            # Upper-case substrings of the 00/ff identity reply
    width: int
    height: int
    control: tuple = (28, 0)   # Heartbeat and simulator-mode destination (type, id)
    identity: tuple = (28, 1)  # Device-info destination
    video: tuple = (28, 1)     # 0b/53 video destination
    tested: bool = False       # Displayed video over the PC route on hardware

    @property
    def size(self):
        return f'{self.width}x{self.height}'


GOGGLES_2 = GogglesModel('DJI Goggles 2', ('ZV900',), 1920, 1080, tested=True)
GOGGLES_INTEGRA = GogglesModel('DJI Goggles Integra', ('ZV901',), 1920, 1080, tested=True)
# ZV902 is Goggles 3, as named by github.com/ggurov/dji-goggles3-display-unit. The Goggles 2
# route reached no video input on the one unit probed; see docs/research/GOGGLES3.md.
GOGGLES_3 = GogglesModel('DJI Goggles 3', ('ZV902',), 1920, 1080)
# Virtual Flight's "Pigeon" profile encodes 1440x810 and sends video to the HD-link ground
# module, DUML type 14 ID 1 (docs/research/MOBILE_PROTOCOL.md). The FPV Goggles V2 panels
# are 1440x810 and DJI's bulk driver binds to that device's interface 4. Untested; see
# docs/research/GOGGLES_V2.md.
FPV_GOGGLES_V2 = GogglesModel('DJI FPV Goggles V2', ('PIGEON', 'GL170'), 1440, 810, video=(14, 1))
# Same panels and platform as V2. Virtual Flight support on V1 is unconfirmed.
FPV_GOGGLES_V1 = GogglesModel('DJI FPV Goggles V1', (), 1440, 810, video=(14, 1))

TESTED = (GOGGLES_2, GOGGLES_INTEGRA)
EXPERIMENTAL = (GOGGLES_3, FPV_GOGGLES_V2, FPV_GOGGLES_V1)
ALL = TESTED + EXPERIMENTAL
BY_NAME = {model.name: model for model in ALL}

# USB product IDs seen on DJI goggles with a bulk DUML interface. 0x0020 is Goggles 2,
# Integra and Goggles 3. DJI's bulk driver INF also claims 0x001f interface 4, and
# fpv.wtf tools identify 0x001f as the FPV Goggles V2.
PRODUCT_IDS = {0x0020: 'Goggles 2, Integra, or Goggles 3', 0x001f: 'FPV Goggles V2 or V1'}


def match_identity(identity, models=ALL):
    """Return the model whose code appears in an identity reply, or None."""
    text = identity.upper()
    for model in models:
        if any(code in text for code in model.codes):
            return model
    return None
