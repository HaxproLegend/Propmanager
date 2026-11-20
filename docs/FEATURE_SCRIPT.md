# PropManager Feature Script

**Purpose:** Short walkthrough script for presenting the brokerage MVP and its three role-based views.  
**Estimated length:** 2–3 minutes

## Opening

“PropManager is a rental brokerage and property operations platform. It brings renters, property owners, and brokers into one application. Owners can manage multiple properties, renters can manage multiple rentals, and brokers coordinate applications and reported issues from a shared operations dashboard. Each account sees the tools and records allowed by its role.”

## Renter view

“As a renter, I can browse available apartments, PGs, hostels, or office and commercial spaces. I can apply to a listing and follow the application decision. When an application is accepted, that rental appears in My Properties. If I rent more than one place, I can see each active rental under the same account.

For an active rental, I can report an issue and choose a category such as maintenance, personal safety, neighbourhood safety, security, or cleanliness. I can add its importance and description, then follow the status as the broker reviews and handles it. I can also view my profile and the commission ledger information associated with my rental.”

## Owner view

“As an owner, I can create and manage multiple listings in My Properties. Each listing records its property type and the number of units or rooms, so the same basic workflow can represent an apartment building, PG or hostel, or office property. I can review applications for my own listings, accept or decline them, and see issue updates relevant to my properties.”

## Broker / Manager view

“As a broker or manager, I use one operations dashboard to coordinate properties, applications, issues, and the commission ledger. The issue queue shows the issue’s importance, how many matching open reports exist, and how many distinct residents submitted those reports. I use those details to decide what to handle first; the MVP does not automatically approve or delay issues.

I can move an issue through Pending, In Progress, and Resolved, or mark it Skipped with a reason. The dashboard summarizes the issue statuses so the team can see what needs attention.”

## Commission explanation

“For the demo, the commission ledger records a recurring monthly amount equal to 10% of rent for the renter and a separate 10% amount for the owner. These entries are tracked by rental, month, and party. They are ledger records only: the MVP does not collect or transfer money, and the monthly amounts are not prorated.”

## Security and closing

“The system uses role-based access so renters, owners, and brokers only get the actions and records intended for their role. Passwords are stored as Argon2id hashes, and the backend uses session and CSRF protections. PropManager’s current goal is to make the rental and issue coordination workflow clear across multiple properties. Legal lease and tenant-benefit wording will be added after our team supplies the approved clauses.”

## Feature scope at a glance

### Core MVP

- Renter, owner, and broker/manager accounts with role-based access.
- Profile page with editable display name.
- Multiple owner listings and multiple renter rentals in one account.
- Listing types for apartments, PG/hostel, and office/commercial properties.
- Listing discovery, rental applications, owner decisions, and broker coordination.
- Issue reporting across maintenance, personal safety, neighbourhood safety, access/security, and facility categories.
- Broker issue queue with priority factors, filters, notes, and Pending / In Progress / Resolved / Skipped lifecycle.
- Recurring monthly ledger entries of 10% of rent for each side of an active rental; no payment processing.

### Stretch / later scope

- Organization and multi-broker accounts for B2B property portfolios.
- Automated payment collection or commission transfers.
- Legal lease documents and tenant-benefit clauses after approved wording is supplied.
- Notifications, in-app messaging, comments, photo attachments, vendors, technician assignment, and visit scheduling.
- Automated numeric or AI issue scoring, analytics, exports, map search, and mobile/offline support.
