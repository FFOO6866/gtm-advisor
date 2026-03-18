/**
 * Display formatting utilities.
 */

/**
 * Words that should stay in a specific form when title-casing.
 * Key = uppercase lookup, Value = desired display form.
 */
const PRESERVE_FORM = new Map<string, string>([
  ['AI', 'AI'], ['ML', 'ML'], ['API', 'API'],
  ['CEO', 'CEO'], ['CTO', 'CTO'], ['CFO', 'CFO'], ['CMO', 'CMO'], ['COO', 'COO'], ['VP', 'VP'],
  ['SAAS', 'SaaS'], ['GTM', 'GTM'], ['SME', 'SME'],
  ['HR', 'HR'], ['IT', 'IT'], ['UI', 'UI'], ['UX', 'UX'],
  ['IOT', 'IoT'], ['AR', 'AR'], ['VR', 'VR'], ['PR', 'PR'], ['HQ', 'HQ'],
]);

/**
 * Title-case a display name, preserving known acronyms.
 *
 * "hi meet ai"   → "Hi Meet AI"
 * "acme pte ltd"  → "Acme Pte Ltd"
 * "ACME PTE LTD"  → "Acme Pte Ltd"
 * "saas platform"  → "SaaS Platform"
 */
export function titleCase(name: string): string {
  if (!name) return name;
  return name
    .split(/\s+/)
    .map((word) => {
      const upper = word.toUpperCase();
      const preserved = PRESERVE_FORM.get(upper);
      if (preserved) return preserved;
      if (word.length === 0) return word;
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
    })
    .join(' ');
}

/**
 * Extract first name from a full name string.
 *
 * "Sarah Chen" → "Sarah"
 * "Sarah"      → "Sarah"
 * ""           → ""
 */
export function firstName(fullName: string | null | undefined): string {
  if (!fullName) return '';
  return fullName.trim().split(/\s+/)[0];
}
