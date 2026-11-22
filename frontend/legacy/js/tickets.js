import{all,put}from'./db.js';
export const createTicket=fields=>put('maintenance_tickets',{...fields,id:crypto.randomUUID(),title:fields.title.trim(),description:fields.description.trim(),status:'Pending',createdAt:new Date().toISOString()});
export async function updateStatus(id,status){const item=(await all('maintenance_tickets')).find(t=>t.id===id);if(!item)throw Error('Ticket not found');item.status=status;return put('maintenance_tickets',item);}
