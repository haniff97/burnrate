// Parse the downloadable text file locally; only the code is sent on recovery.
export function parseRecoveryFile(text) {
  if (typeof text !== 'string' || text.length > 16384) throw new Error('Choose a recovery text file smaller than 16 KB.');
  const codes = new Set();
  for (const line of text.split(/\r?\n/)) {
    const value = line.trim().toUpperCase();
    if (/^(?:BR-?)?(?:[0-9A-F]{8}-){3}[0-9A-F]{8}$/.test(value) || /^(?:BR-?)?[0-9A-F]{32}$/.test(value)) {
      const canonical = value.replace(/^BR-?/, '').replaceAll('-', '');
      codes.add('BR-' + canonical.match(/.{8}/g).join('-'));
    }
  }
  if (codes.size !== 1) throw new Error(codes.size ? 'This file contains multiple recovery codes. Choose the file for one journal.' : 'No recovery code found. Choose the .txt file downloaded from BurnRate.');
  return [...codes][0];
}
