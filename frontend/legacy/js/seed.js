import { all, put } from './db.js';

const seedRecords = {
  properties: [
    { id: 'p1', name: 'Maple Court', address: '18 Willow Lane, Pune' },
    { id: 'p2', name: 'Cedar House', address: '42 Garden Road, Pune' }
  ],
  units: [
    { id: 'u101', propertyId: 'p1', label: 'A-101', tenantId: 't1' },
    { id: 'u102', propertyId: 'p1', label: 'A-102', tenantId: 't2' },
    { id: 'u103', propertyId: 'p1', label: 'A-103', tenantId: 't3' },
    { id: 'u104', propertyId: 'p1', label: 'A-104', tenantId: 't4' },
    { id: 'u201', propertyId: 'p2', label: 'B-201', tenantId: 't5' },
    { id: 'u202', propertyId: 'p2', label: 'B-202', tenantId: 't6' },
    { id: 'u203', propertyId: 'p2', label: 'B-203', tenantId: null },
    { id: 'u204', propertyId: 'p2', label: 'B-204', tenantId: null }
  ],
  tenants: [
    { id: 't1', name: 'Avery Shah', unitId: 'u101' },
    { id: 't2', name: 'Jordan Mehta', unitId: 'u102' },
    { id: 't3', name: 'Riya Patel', unitId: 'u103' },
    { id: 't4', name: 'Samir Desai', unitId: 'u104' },
    { id: 't5', name: 'Maya Rao', unitId: 'u201' },
    { id: 't6', name: 'Kabir Joshi', unitId: 'u202' }
  ],
  maintenance_tickets: [
    { id: 'm1', title: 'Kitchen sink is leaking', description: 'Water is dripping below the kitchen sink.', unitId: 'u101', tenantId: 't1', priority: 'High', status: 'Pending', createdAt: '2026-11-01T09:00:00.000Z' },
    { id: 'm2', title: 'Bedroom light not working', description: 'The ceiling light stopped working.', unitId: 'u102', tenantId: 't2', priority: 'Medium', status: 'In Progress', createdAt: '2026-11-02T10:30:00.000Z' },
    { id: 'm3', title: 'Front door lock is stiff', description: 'The key is difficult to turn in the lock.', unitId: 'u201', tenantId: 't5', priority: 'Low', status: 'Resolved', createdAt: '2026-11-03T11:15:00.000Z' },
    { id: 'm4', title: 'Bathroom tap needs repair', description: 'Tap continues to drip after closing.', unitId: 'u103', tenantId: 't3', priority: 'Medium', status: 'Pending', createdAt: '2026-11-04T08:45:00.000Z' },
    { id: 'm5', title: 'Balcony drain is blocked', description: 'Rain water is draining slowly from the balcony.', unitId: 'u202', tenantId: 't6', priority: 'High', status: 'In Progress', createdAt: '2026-11-05T13:20:00.000Z' },
    { id: 'm6', title: 'Window latch is loose', description: 'The living room window latch does not hold.', unitId: 'u104', tenantId: 't4', priority: 'Low', status: 'Resolved', createdAt: '2026-11-06T15:00:00.000Z' }
  ]
};

export async function seedIfEmpty() {
  for (const [storeName, records] of Object.entries(seedRecords)) {
    if ((await all(storeName)).length === 0) {
      for (const record of records) await put(storeName, record);
    }
  }
}

// Backward-compatible name used by the current app entry point.
export const seed = seedIfEmpty;
