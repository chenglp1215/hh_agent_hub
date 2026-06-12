---
name: antd-dark-theme-css
description: Ant Design Vue components need explicit dark theme CSS overrides for 20+ component classes
metadata:
  type: project
---

Ant Design Vue defaults to light theme colors (white backgrounds, dark text). The project uses Linear dark design system (`#010102` canvas / `#0a0a0b` surface). Simply setting dark body background is not enough — each Ant Design component's internal CSS classes need explicit overrides.

**Why:** Missing overrides cause invisible text (black on black), white boxes on dark backgrounds, and inconsistent styling.

**How to apply:** When adding ANY new Ant Design component to a page, check if its CSS classes are covered in `frontend/src/style.css`. If not, add dark background + light text (`#e1e1e1`) overrides. Currently covered as of 2026-06-11: button (6 variants), input/affix/password, select/dropdown, card, table, modal, tag, form-item, spin, empty, checkbox, breadcrumb, result, divider, pagination, switch, tabs, message/notification, drawer, dropdown, tooltip, badge, steps, radio, tree, input-number, popover/popconfirm.

Related: [[linear-design-system]]
