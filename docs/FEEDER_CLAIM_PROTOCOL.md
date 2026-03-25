# Feeder claim protocol (TAKNET-PS aggregator)

This feeder implements optional identity metadata lines on the Beast TCP stream to the aggregator (port 30004 by default):

- `TAKNET_FEEDER_CLAIM <uuid>`
- `TAKNET_FEEDER_MAC <aa:bb:cc:dd:ee:ff>`

## Configuration

- **Web UI:** Settings → **Aggregator feeder claim key** (stored as `TAKNET_PS_FEEDER_CLAIM_KEY` in `.env`).
- **Format:** Standard UUID `8-4-4-4-12` hex. Empty = legacy behavior (no claim line; first byte on the wire is Beast `0x1A`).
- **Optional MAC:** set `TAKNET_PS_FEEDER_MAC` in `.env` to send a stable feeder MAC identity line.

## Implementation on this feeder

readsb does not support ASCII metadata prefixes on outbound Beast connections. When a valid claim key is set and TAKNET-PS is enabled, `config_builder.py`:

1. Adds a Docker service **`taknet-beast-claim`** running `scripts/beast_claim_proxy.py` (Python stdlib TCP bridge).
2. Points the TAKNET-PS **Beast** `ULTRAFEEDER_CONFIG` entry at `taknet-beast-claim:39904` instead of the aggregator host directly.
3. The proxy connects to the selected aggregator host (VPN or public, same logic as before), sends metadata lines before Beast bytes:
   - `TAKNET_FEEDER_CLAIM <uuid>\n` (UUID lowercase) when claim key is valid
   - `TAKNET_FEEDER_MAC <aa:bb:cc:dd:ee:ff>\n` when MAC is set/valid
   then forwards bytes **both ways**.

MLAT is unchanged (still connects directly to the aggregator MLAT port).

## References

- Aggregator behavior: first byte `0x1A` → legacy Beast; first byte `T` → read line and parse claim; invalid keys still accept the feed (no TCP error).

See repository `README.md` (network / aggregator section) for operator-facing notes.
