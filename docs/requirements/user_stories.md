# User stories

User stories for the Ekte Mat ordering system, with acceptance criteria. Each story cites its source; decisions refer
to the [decisions log](../decisions.md). Statuses and transitions follow the [state diagrams](../diagrams/state_order.md),
and the data behind each story is in the [data model](../diagrams/data_model.md).

**Priority (MoSCoW):** **M** = must have for go-live 1 March 2027 · **S** = should have · **C** = could have, if time allows.

**Roles:** *visitor* (not logged in) · *customer* (private, logged in) · *company user* (logged in, belongs to a company) ·
*company approver* · *admin* (Ekte Mat coordinator) · *kitchen* · *driver*.

Main sources: `basic_desc.txt` (BD), stakeholder interviews (Ingrid, Sunniva, Mateo, Fjordtek), GDPR note, decisions 2026-10-27.

## Overview

| Epic | Stories | Must | Should | Could |
|---|---|---|---|---|
| E1 Menus | US-01 – US-03 | 2 | 0 | 1 |
| E2 Account and ordering | US-04 – US-12 | 8 | 1 | 0 |
| E3 Corporate accounts | US-13 – US-17 | 3 | 1 | 1 |
| E4 Admin: catalogue | US-18 – US-20 | 3 | 0 | 0 |
| E5 Admin: orders | US-21 – US-26 | 5 | 1 | 0 |
| E6 Kitchen | US-27 – US-29 | 2 | 0 | 1 |
| E7 Delivery | US-30 | 1 | 0 | 0 |
| E8 Privacy | US-31 | 0 | 1 | 0 |

---

## E1 Menus

### US-01 Browse menus by event type · M
As a **visitor**, I want to see the menus grouped by type of event, so that I can find food that suits my event.
*Source: BD customer side "Menu by event"; Ingrid interview (self-service at any hour).*
- Given published food items linked to event types, when I open the menu page, then I see one section per event type (birthday, confirmation, wedding, conference, christmas party, corporate lunch).
- Each card shows an approved image, the name, the price in NOK, the minimum order, allergens and diet information.
- The minimum shown is the event type's **current** minimum.
- Unpublished food items and images not yet approved are never shown.

### US-02 Choose language · M
As a **visitor**, I want to switch between Norwegian and English, so that I can read the menu and order in my own language.
*Source: decision 2026-10-27; `current_IT_landscape.txt`.*
- Given any page, when I choose "English" or "Norsk", then all texts, menu names and descriptions are shown in that language.
- My choice is remembered while I browse, and is saved on my account if I'm logged in.

### US-03 Filter by diet and allergens · C
As a **health-conscious customer**, I want to filter the menu by diet and hide dishes with certain allergens, so that I quickly find food I can eat.
*Source: kick-off notes (customer group "health-conscious"); BD "diet implications".*
- When I select a diet (for example vegetarian), only dishes that fit it are shown.
- When I exclude an allergen (for example nuts), dishes containing it are hidden.

## E2 Account and ordering

### US-04 Register and log in · M
As a **visitor**, I want to register and log in with my e-mail address and a password, so that my orders are saved on my account.
*Source: BD login section; decision 2026-10-27 (basic login).*
- The e-mail address must be unique; registering with an existing address gives a clear message.
- Passwords are stored hashed, never in plain text.
- Given a registered account, when I log in with the right e-mail and password, then I'm logged in; with the wrong ones I see an error that doesn't reveal which one was wrong.
- **Not in this version:** password reset by e-mail (decision 2026-10-27).

### US-05 Shopping cart · M
As a **customer**, I want to add dishes to a cart, change the quantities and see the total cost, so that I know what I'm ordering and what it costs.
*Source: BD "A shopping cart".*
- I can add a dish, change its quantity and remove it.
- The total in NOK updates after every change.
- The cart is kept while I log in or register.

### US-06 Minimum order check · M
As **Ekte Mat**, we want orders below the event type's minimum to be stopped, so that we don't take orders that aren't worth delivering.
*Source: BD "orders below minimum order limit should be rejected"; BD event-type lower limit.*
- Given an event type with minimum 20, when the order has 19 guests, then it can't be submitted and I see the minimum.
- Given 20 or more guests, the order can be submitted.
- Each dish's own minimum order quantity is also checked.
- The minimum in force when the order is submitted is saved on the order (`min_guests_at_order`).

### US-07 Submit an order · M
As a **customer**, I want to submit my order with all event details, so that Ekte Mat has everything needed to deliver.
*Source: BD "Submit order"; Sunniva interview (allergies per guest group); GDPR note; BD payment option.*
- The order form asks for event type, event date, number of guests, delivery address, delivery notes and payment option (invoice, Vipps or bank transfer).
- Allergies and diets are entered **per guest group** (for example "4 guests: gluten-free"), never per named guest.
- The event date must be more than 5 days ahead (assumption, so the order isn't locked as soon as it's placed; confirm with Ingrid).
- When I submit, the order gets status **Submitted** (or **Awaiting company approval**, see US-14) and I get a confirmation e-mail.

### US-08 See my orders · M
As a **customer**, I want to see my current and past orders, so that I can keep track of them.
*Source: BD "All orders should be accessible for the user".*
- My order page lists current orders and past orders separately, with status and payment status.
- Past orders (delivered, cancelled, rejected) are read-only: no edit or cancel buttons, and the server refuses changes.

### US-09 Change an order · M
As a **customer**, I want to change the number of guests or dishes in my order, so that it matches my final guest list.
*Source: BD 5-day limit; Sunniva interview (guest numbers change).*
- Given an order in **Submitted** or **Approved** with more than 5 days left, I can change guests, dishes, guest groups and delivery notes.
- The new number of guests must be at least the **saved** minimum, even if the event type's minimum has changed since.
- When an approved order is changed, the admin is notified.
- With 5 days or less left, changes are refused and I'm shown how to ask a question instead (US-12).

### US-10 Cancel an order · M
As a **customer**, I want to cancel my order, so that I don't pay for an event that isn't happening.
*Source: BD "An order could be cancelled up until 5 days before event".*
- Given an approved order with more than 5 days left, when I cancel and confirm, then the status becomes **Cancelled** and the admin is notified.
- With 5 days or less left, the cancel button isn't shown and the server refuses the request.
- *Open question:* can a **submitted** (not yet approved) order be cancelled? See `state_order.md`.

### US-11 Reminder 7 days before · M
As a **customer**, I want a reminder 7 days before my event, so that I can update or cancel before the 5-day limit.
*Source: BD reminder; Sunniva interview.*
- For every approved order, an e-mail is sent once, 7 days before the event, with a link to the order and the date of the 5-day limit.
- Cancelled and rejected orders get no reminder.

### US-12 Ask a question about an order · S
As a **customer**, I want to send a question about one of my orders and read the answer, so that I don't have to call or e-mail.
*Source: BD "Submit a questions about a selected order".*
- From an order page I can write a question; it's stored with the order.
- The admin's answer is shown on the same order page, and I get an e-mail saying an answer is ready.

## E3 Corporate accounts

### US-13 Company account · M
As an **admin**, I want to create a company account and add its users and approver, so that several people at a company can order on one account.
*Source: decision 2026-10-27 (corporate accounts); Fjordtek interview.*
- A company has a name, organisation number, invoice e-mail and an approval limit in NOK (default 15 000).
- Customers can be linked to a company as **orderer** or **approver**.
- Company users see all orders for their company, not only their own.

### US-14 Approval above the limit · M
As a **company approver**, I want orders above our approval limit to need my approval, so that we control larger costs.
*Source: Fjordtek interview ("only I should approve anything above 15 000 NOK"); decision 2026-10-27.*
- Given a company order with a total above the company's limit, when a company user submits it, then the status is **Awaiting company approval** and the approver is e-mailed.
- Orders at or below the limit go straight to **Submitted**.

### US-15 Approve or decline · M
As a **company approver**, I want to approve or decline orders waiting for me, so that they go to Ekte Mat or are stopped.
*Source: Fjordtek interview; order state diagram.*
- I see a list of my company's orders awaiting approval.
- Approving sets the status to **Submitted**; declining requires a reason and sets it to **Rejected**. The orderer is e-mailed either way.

### US-16 Cost-centre code and monthly invoice · S
As a **company user**, I want to add our cost-centre code to each order, and my company wants one invoice per month, so that our finance department can process it.
*Source: Fjordtek interview; Sunniva interview (EHF monthly invoice).*
- The order form has a cost-centre field for company users.
- The admin can list a company's delivered orders for a month, with cost-centre codes, to make the monthly invoice in Fiken.
- Payment status for those orders is set to **Invoiced** when the invoice is sent.

### US-17 Copy last order · C
As a **company user**, I want to copy a previous order, so that I don't have to enter weekly lunches again.
*Source: Fjordtek interview ("copy last week's order").*
- From a past order I can choose "Order again", which fills a new cart with the same dishes, guests and guest groups; I only pick a new date.

## E4 Admin: catalogue

### US-18 Manage food items · M
As an **admin**, I want to add and edit food items, so that the menu is always correct.
*Source: BD admin "Food items"; Mateo interview (menus change 4 times a year).*
- A food item has a name and description in Norwegian and English, a price in NOK, a minimum order quantity, one or more event types, allergens and diets.
- I can publish or unpublish an item; only published items are shown to customers.
- Changing a price doesn't change orders already placed (prices are saved on each order line).

### US-19 Upload and review images · M
As an **admin**, I want to upload images of a dish and review them before they're public, so that only good photos are shown.
*Source: BD "Images".*
- I can upload one or more images per food item; new images get status **pending**.
- I can approve or reject each image; only approved images are shown to customers.

### US-20 Manage event types and minimums · M
As an **admin**, I want to see the event types and change each one's minimum number of guests, so that the limits match what we can deliver.
*Source: BD "Event-type"; placeholder values per decision 2026-10-27.*
- I can set a minimum from 1 to 265; other values are refused with a message.
- Changing a minimum doesn't affect orders already submitted (US-06).
- *Implemented in the backend:* `PUT /api/event-types/<id>/minimum`.

## E5 Admin: orders

### US-21 Order list · M
As an **admin**, I want a list of all orders that I can filter by status and event date, so that I can find what needs attention.
*Source: BD admin "Orders".*
- I can filter by one or more statuses and a date range for the event date.
- Each row shows event date, customer or company, event type, guests, status and payment status.

### US-22 Approve or reject an order · M
As an **admin**, I want to open an order and approve or reject it, so that the customer gets a quick answer.
*Source: BD order page and statuses; Ingrid interview (lost inquiries, slow replies).*
- The order page shows all order details, guest groups with allergies, and questions.
- Approving sets **Approved**; rejecting requires a reason and sets **Rejected**. The customer is e-mailed either way.

### US-23 Capacity per day · S
As an **admin**, I want to see how many guests we already have on a given day, so that we don't overbook.
*Source: Sunniva interview (400 covers a day, 250 with a served wedding dinner).*
- The order page and order list show the total guests for that event date.
- A warning is shown when approving would exceed 400 guests that day, or 250 if a wedding is booked that day.

### US-24 Payment status · M
As an **admin**, I want to set the payment status of an order by hand, so that we know what has been paid.
*Source: BD payment status; payment state diagram; decision 2026-10-27 (no deposits).*
- Allowed changes: not paid → invoiced, not paid → paid, invoiced → paid.
- The customer's chosen payment option is shown next to the payment status.

### US-25 Release to kitchen · M
As an **admin**, I want to release locked orders to the kitchen, so that the kitchen knows what to prepare.
*Source: order state diagram; flowchart 2.*
- 5 days before the event, approved orders are locked automatically (no more changes or cancellations).
- I can release a locked order, which sets **In preparation** and shows it on the kitchen screen.

### US-26 Answer questions · M
As an **admin**, I want to see and answer customers' questions about their orders, so that customers get answers in one place.
*Source: BD admin "Questions".*
- I see a list of unanswered questions, newest first, with a link to the order.
- My answer is saved on the order and the customer is e-mailed.

## E6 Kitchen

### US-27 Kitchen screen · M
As **kitchen staff**, I want a tablet screen that shows each day's orders, portions per dish and allergies in red, so that we prepare the right food.
*Source: Mateo interview; decision 2026-10-27 (kitchen screen in scope).*
- I log in with a short PIN instead of a long password.
- For a chosen day, I see each order in preparation, the number of portions per dish, and guest groups with allergies highlighted in red.
- Pages load quickly (Mateo: the old booking plugin took 10 seconds).

### US-28 Confirm allergies seen · M
As **kitchen staff**, I want to confirm that I've seen an order's allergies, so that the coordinator knows they've been checked.
*Source: Sunniva interview ("the kitchen must confirm they have seen it").*
- Each order with allergies has a "Seen" button; pressing it stores who confirmed and when.
- The admin's order page shows whether the allergies are confirmed.

### US-29 Prep list and offline view · C
As **kitchen staff**, I want a list of total ingredients for the next 3 days, and today's orders still visible if the internet is down.
*Source: Mateo interview.*
- The prep list sums ingredient quantities across orders for the next 3 days. (Needs ingredients and recipes, which aren't in the data model yet.)
- Today's orders are kept on the tablet and shown when the connection is lost, with a "last updated" time.

## E7 Delivery

### US-30 Driver screen · M
As a **driver**, I want to see today's deliveries with addresses and delivery notes and confirm each delivery, so that orders are marked as delivered.
*Source: flowchart 2; decision 2026-10-27 (driver screen in scope); as-is process step 10.*
- I see today's orders in preparation with event time, address and delivery notes, and a link to open the address in a map.
- When I confirm a delivery, the status becomes **Delivered** and the order becomes read-only.

## E8 Privacy

### US-31 Access and deletion · S
As a **customer**, I want to see the data stored about me and ask for it to be deleted, so that my privacy rights are respected.
*Source: GDPR note; Fjordtek interview (delete employees' names when they leave).*
- I can download my account data and order history.
- When I ask for deletion, my name, e-mail and phone are removed or anonymised; order data needed for bookkeeping is kept for 5 years without my personal details.
- When a company leaves, its users' names are deleted in the same way.
