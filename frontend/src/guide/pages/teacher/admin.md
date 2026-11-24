---
title: Admin
summary: People and accounts: roles from addresses, role overrides, adding teachers early, and every teacher's Roll Call register.
order: 10
keywords: [admin, people, accounts, roles, teacher, student, override, reset, ta, registers, access]
---

Admins are addresses listed in the server's `STUDENTIDE_ADMINS` setting. They are teachers who can also open **People** (`#/teach/people`).

## Roles

Roles come from the address, so nothing has to be set up by hand:

- A student-shaped address (`ug…` / `pg…`) is a **student**; the whole part before the `@`, in capitals, is their id.
- Any other college address is a **teacher**.
- Admins are always admins.

## People

**People** lists accounts with a search box. Change a role from the dropdown, for example to make a TA's student address a teacher, or to make a staff address a student. An override sticks at every sign-in until you press **Reset**. Demoting a teacher signs them out at once. A role fixed by the server's admin list shows dimmed and cannot be changed here.

**Add a teacher before their first sign-in** by entering their college address.

## Lab ownership

Admins see every lab and every session. They can hand over a lab that has no owner (made before ownership) in its **Teachers** panel, and are the only ones who can change an owner.

## Roll Call registers

Under **Teachers' Roll Call registers** (People and Getting started) an admin can open any teacher's register with full access. Roll Call shows a banner naming whose register it is, and every open is logged.

## Good practice

Use admin rights sparingly, tell teachers that admins can see their labs, and keep the research token empty in production.
