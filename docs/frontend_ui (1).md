# Enterprise HR Platform Design System

This design system is based on a **modern enterprise SaaS application** similar to platforms like **Workday**, **SAP SuccessFactors**, **Oracle**, and **Rippling**, with a premium, minimal aesthetic.

---

# 1. Design Philosophy

The UI follows these principles:

* Minimal
* Professional
* Enterprise-grade
* High readability
* Spacious layouts
* Soft shadows
* Consistent spacing
* Neutral backgrounds
* Single accent color
* Information hierarchy

Avoid:

* Bright gradients
* Neon colors
* Heavy animations
* Excessive icons
* Visual clutter

The application should feel like a product used by HR executives, managers, and corporate employees.

---

# 2. Color Palette

## Primary Color

```text
#14213D
```

Used for

* Sidebar
* Primary buttons
* Headings
* Active navigation
* Important text

RGB

```text
20,33,61
```

---

## Accent Color

```text
#D9A653
```

Used for

* Highlights
* Hover states
* Active indicators
* Small headings
* Links
* Progress indicators

RGB

```text
217,166,83
```

---

## Background

```text
#FAFAF9
```

Used for

Entire application background

This keeps the interface soft instead of pure white.

---

## Card Background

```text
#FFFFFF
```

Every card uses white.

---

## Border

```text
#E5E7EB
```

All cards

Tables

Inputs

Containers

---

## Divider

```text
rgba(255,255,255,0.1)
```

Sidebar separators.

---

# Text Colors

Primary

```text
#14213D
```

Secondary

```text
#6B7280
```

Muted

```text
#9CA3AF
```

Disabled

```text
#D1D5DB
```

---

# Status Colors

## Success

Background

```text
#DCFCE7
```

Text

```text
#166534
```

---

## Warning

Background

```text
#FEF3C7
```

Text

```text
#92400E
```

---

## Error

Background

```text
#FEE2E2
```

Text

```text
#991B1B
```

---

## Information

Background

```text
#DBEAFE
```

Text

```text
#1D4ED8
```

---

# Sidebar

Width

```text
288px
```

(Tailwind)

```text
w-72
```

Background

```text
#14213D
```

Padding

```text
32px
```

Navigation item

```text
padding:16px

border-radius:12px
```

Active item

```text
background:white 10% opacity
```

Inactive

```text
70% opacity
```

---

# Header

Height

```text
80px
```

Layout

```text
Display:flex

justify-content:space-between

align-items:center
```

---

# Cards

Border Radius

```text
16px
```

Tailwind

```text
rounded-2xl
```

Shadow

```text
shadow-sm
```

Hover

```text
hover:shadow-md
```

Padding

```text
24px
```

Background

White

---

# Buttons

Primary

```text
Background

#14213D

Text

White
```

Hover

```text
#D9A653
```

Disabled

```text
opacity:60%
```

Radius

```text
12px
```

Padding

```text
20px 12px
```

Transition

```css
transition:0.3s
```

---

# Inputs

Height

```text
48px
```

Radius

```text
12px
```

Border

```text
1px #E5E7EB
```

Focus

```text
2px Accent Color
```

Padding

```text
16px
```

---

# Tables

Header

```text
Background

Gray 50
```

Rows

White

Hover

```text
Gray 50
```

Border

Bottom only

```text
#E5E7EB
```

Padding

```text
16px
```

---

# Badges

Radius

```text
9999px
```

Padding

```text
12px
```

Font

```text
12px
```

Weight

```text
600
```

---

# Avatar

Circle

```text
44px
```

Background

```text
#14213D
```

Text

White

Weight

Bold

---

# Typography

Font

```text
Inter
```

Fallback

```text
system-ui
```

---

## Hero Heading

```text
48px

Bold
```

---

## Page Heading

```text
36px

Bold
```

---

## Card Number

```text
40px

Bold
```

---

## Card Title

```text
14px

Medium
```

---

## Body

```text
16px
```

---

## Small

```text
14px
```

---

## Caption

```text
12px
```

---

# Border Radius Standards

Buttons

```text
12px
```

Inputs

```text
12px
```

Cards

```text
16px
```

Tables

```text
16px
```

Avatars

```text
50%
```

---

# Spacing Scale

```text
4

8

12

16

24

32

48

64
```

Never use random spacing.

---

# Grid

Desktop

```text
Sidebar

288px

Content

Remaining Width
```

Dashboard Cards

```text
3 columns
```

Large Screen

```text
6 KPI cards
```

Tablet

```text
2 columns
```

Mobile

```text
1 column
```

---

# Animation

Duration

```text
300ms
```

Hover

```text
Shadow Increase

Button Color

Row Background
```

Avoid

Bounce

Scale

Large transitions

---

# Icons

Recommended

* Lucide
* Heroicons

Avoid mixing multiple icon packs.

---

# Charts

Library

* Recharts

Department Chart

```text
Bar Color

#D9A653
```

Role Chart

```text
Bar Color

#14213D
```

Rounded Bars

```text
8px
```

Grid

Light Gray

Tooltip

White

---

# Responsive Breakpoints

```text
sm

640px
```

```text
md

768px
```

```text
lg

1024px
```

```text
xl

1280px
```

Sidebar

Hidden below

```text
1024px
```

---

# Accessibility

Minimum contrast ratio for text.

Clickable targets ≥44×44 px.

Visible focus state on interactive elements.

Semantic HTML (`<main>`, `<nav>`, `<button>`, `<table>`, headings in order).

---

# Naming Convention

Use reusable components rather than styling every page independently:

```text
components/
├── Sidebar.tsx
├── TopBar.tsx
├── PageHeader.tsx
├── StatCard.tsx
├── SearchBar.tsx
├── StatusBadge.tsx
├── SourceBadge.tsx
├── Avatar.tsx
├── DataTable.tsx
├── EmptyState.tsx
├── LoadingSpinner.tsx
└── Layout.tsx
```

---

# Tailwind Utility Standards

Prefer these consistently:

* Layout: `flex`, `grid`, `gap-4`, `gap-6`, `items-center`, `justify-between`
* Spacing: `p-4`, `p-6`, `p-8`, `mt-4`, `mt-6`, `mt-8`
* Containers: `rounded-2xl`, `border`, `bg-white`, `shadow-sm`
* Typography: `text-sm`, `text-lg`, `text-2xl`, `text-4xl`, `font-semibold`, `font-bold`
* Interaction: `hover:shadow-md`, `hover:bg-gray-50`, `transition`, `duration-300`
* Forms: `focus:outline-none`, `focus:ring-2`, `focus:ring-[#D9A653]`

---

# Overall Visual Identity

The application should communicate:

* Trustworthy
* Professional
* Clean
* Modern
* Executive-focused
* Data-driven
* Calm rather than flashy

