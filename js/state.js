const ROLE_KEY = 'propmanager.role';
const TENANT_ID_KEY = 'propmanager.tenantId';
const DEFAULT_TENANT_ID = 't1';

export function getRole() {
  const storedRole = localStorage.getItem(ROLE_KEY);
  return storedRole === 'manager' || storedRole === 'tenant' ? storedRole : 'tenant';
}

export function setRole(role) {
  if (!['tenant', 'manager'].includes(role)) throw new Error('Role must be tenant or manager.');
  localStorage.setItem(ROLE_KEY, role);
}

export function getTenantId() {
  return localStorage.getItem(TENANT_ID_KEY) || DEFAULT_TENANT_ID;
}

// Compatibility exports used by the existing app entry point.
export const role = getRole;
export const saveRole = setRole;
export const tenantId = getTenantId;
