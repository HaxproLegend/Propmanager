const DATABASE_NAME = 'propmanager-db';
const DATABASE_VERSION = 1;

const STORE_DEFINITIONS = {
  properties: { keyPath: 'id', indexes: [['name', 'name', { unique: false }]] },
  units: {
    keyPath: 'id',
    indexes: [['propertyId', 'propertyId', { unique: false }], ['tenantId', 'tenantId', { unique: false }]]
  },
  tenants: { keyPath: 'id', indexes: [['unitId', 'unitId', { unique: false }]] },
  maintenance_tickets: {
    keyPath: 'id',
    indexes: [['unitId', 'unitId', { unique: false }], ['tenantId', 'tenantId', { unique: false }], ['status', 'status', { unique: false }], ['createdAt', 'createdAt', { unique: false }]]
  }
};

let databasePromise;

export function openDB() {
  if (databasePromise) return databasePromise;

  databasePromise = new Promise((resolve, reject) => {
    if (!('indexedDB' in window)) {
      reject(new Error('IndexedDB is not available in this browser.'));
      return;
    }

    const request = indexedDB.open(DATABASE_NAME, DATABASE_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      for (const [storeName, definition] of Object.entries(STORE_DEFINITIONS)) {
        const store = db.objectStoreNames.contains(storeName)
          ? request.transaction.objectStore(storeName)
          : db.createObjectStore(storeName, { keyPath: definition.keyPath });
        for (const [indexName, keyPath, options] of definition.indexes) {
          if (!store.indexNames.contains(indexName)) store.createIndex(indexName, keyPath, options);
        }
      }
    };
    request.onsuccess = () => {
      const db = request.result;
      db.onversionchange = () => db.close();
      resolve(db);
    };
    request.onerror = () => reject(request.error || new Error('Could not open the local database.'));
    request.onblocked = () => reject(new Error('Database upgrade is blocked. Close other PropManager tabs and reload.'));
  }).catch(error => {
    databasePromise = null;
    throw error;
  });

  return databasePromise;
}

export async function all(storeName) {
  const db = await openDB();
  return runRequest(db, storeName, 'readonly', store => store.getAll());
}

export async function put(storeName, record) {
  const db = await openDB();
  return runRequest(db, storeName, 'readwrite', store => store.put(record)).then(() => record);
}

export async function count(storeName) {
  const db = await openDB();
  return runRequest(db, storeName, 'readonly', store => store.count());
}

function runRequest(db, storeName, mode, createRequest) {
  if (!db.objectStoreNames.contains(storeName)) return Promise.reject(new Error(`Unknown data store: ${storeName}`));
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(storeName, mode);
    const request = createRequest(transaction.objectStore(storeName));
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error(`Database request failed for ${storeName}.`));
    transaction.onabort = () => reject(transaction.error || new Error(`Database transaction failed for ${storeName}.`));
  });
}
