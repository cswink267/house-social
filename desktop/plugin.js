import { useEffect, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

function knownCount(brand) {
  return (brand.channels || []).filter((channel) => channel.known).length
}

function HousePane({ ctx }) {
  const [brands, setBrands] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    let gone = false
    ctx.rest('/roster')
      .then((data) => {
        if (!gone) setBrands(data.brands || [])
      })
      .catch((err) => {
        if (!gone) setError(err && err.message ? err.message : String(err))
      })
    return () => {
      gone = true
    }
  }, [ctx])

  return jsxs('div', {
    className: 'flex h-full flex-col gap-2 overflow-auto p-3 text-sm',
    children: [
      jsx('div', { className: 'font-medium', children: 'House Social' }),
      jsx('div', {
        className: 'text-(--ui-text-tertiary)',
        children: 'Drafts stay local. Open the dashboard for the full composer and brand desks. Nothing is sent.'
      }),
      error ? jsx('div', { children: error }) : null,
      ...brands.map((brand) => jsxs('div', {
        children: [
          jsx('div', { children: brand.name }),
          jsx('div', {
            className: 'text-(--ui-text-tertiary)',
            children: `${knownCount(brand)} of 3 channels known`
          })
        ]
      }, brand.id))
    ]
  })
}

export default {
  id: 'house-social',
  name: 'House Social',
  register(ctx) {
    ctx.register({
      id: 'pane',
      area: 'panes',
      title: 'House Social',
      data: { placement: 'right', width: '280px' },
      render: () => jsx(HousePane, { ctx })
    })
  }
}
