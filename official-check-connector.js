// v2.4 interface only: official sources must be configured server-side.
export async function verifyOfficial({entityHint, phoneHint, urlHint}) {
  // Return: {status:'verified|mismatch|unknown', officialName, officialContact, officialUrl, evidence[]}
  // Never treat the phone/url contained in a suspicious message as official merely because it is present.
  throw new Error('OFFICIAL_CHECK_CONNECTOR_NOT_CONFIGURED');
}
