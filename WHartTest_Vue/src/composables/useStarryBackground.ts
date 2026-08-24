import { onMounted, onUnmounted, type Ref } from 'vue'

interface Star {
  x: number
  y: number
  size: number
  opacity: number
  twinkleSpeed: number
  twinklePhase: number
}

interface Meteor {
  x: number
  y: number
  length: number
  speed: number
  opacity: number
  angle: number
  thickness: number
  life: number
  maxLife: number
}

export function useStarryBackground(canvasRef: Ref<HTMLCanvasElement | null>) {
  interface PlexusNode {
    x: number
    y: number
    vx: number
    vy: number
    radius: number
    baseRadius: number
    opacity: number
  }

  let animationId: number
  let stars: Star[] = []
  let meteors: Meteor[] = []
  let plexusNodes: PlexusNode[] = []
  let ctx: CanvasRenderingContext2D | null = null
  let width = 0
  let height = 0
  const mouse = { x: -1000, y: -1000, active: false }

  function initCanvas() {
    const canvas = canvasRef.value
    if (!canvas) return
    ctx = canvas.getContext('2d')
    resize()
    initStars()
    initPlexus()
  }

  function resize() {
    const canvas = canvasRef.value
    if (!canvas) return
    const dpr = window.devicePixelRatio || 1
    width = window.innerWidth
    height = window.innerHeight
    canvas.width = width * dpr
    canvas.height = height * dpr
    canvas.style.width = `${width}px`
    canvas.style.height = `${height}px`
    ctx?.scale(dpr, dpr)
  }

  function initStars() {
    const count = Math.floor((width * height) / 2000)
    stars = Array.from({ length: count }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      size: Math.random() * 1.8 + 0.3,
      opacity: Math.random() * 0.8 + 0.2,
      twinkleSpeed: Math.random() * 0.02 + 0.005,
      twinklePhase: Math.random() * Math.PI * 2,
    }))
  }

  function initPlexus() {
    const count = Math.min(Math.floor((width * height) / 4800), 260)
    plexusNodes = Array.from({ length: count }, () => {
      const baseRadius = Math.random() * 2.2 + 1.2
      return {
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.42,
        vy: (Math.random() - 0.5) * 0.42,
        radius: baseRadius,
        baseRadius,
        opacity: Math.random() * 0.45 + 0.35,
      }
    })
  }

  function spawnMeteor() {
    const angle = Math.PI / 2 + (Math.random() - 0.5) * 0.3
    meteors.push({
      x: Math.random() * width * 1.2 - width * 0.1,
      y: -20,
      length: Math.random() * 120 + 60,
      speed: Math.random() * 4 + 3,
      opacity: Math.random() * 0.6 + 0.4,
      angle,
      thickness: Math.random() * 1.5 + 0.5,
      life: 0,
      maxLife: Math.random() * 120 + 80,
    })
  }

  function drawStars(time: number) {
    if (!ctx) return
    for (const star of stars) {
      const flicker = Math.sin(time * star.twinkleSpeed + star.twinklePhase)
      const alpha = star.opacity * (0.6 + 0.4 * flicker)
      ctx.beginPath()
      ctx.arc(star.x, star.y, star.size, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(255, 255, 255, ${alpha})`
      ctx.fill()
    }
  }

  function drawMeteors() {
    if (!ctx) return
    meteors = meteors.filter((m) => {
      m.life++
      m.x += Math.cos(m.angle) * m.speed
      m.y += Math.sin(m.angle) * m.speed

      const fadeRatio = 1 - m.life / m.maxLife
      if (fadeRatio <= 0 || m.y > height + 50) return false

      const alpha = m.opacity * fadeRatio
      const tailX = m.x - Math.cos(m.angle) * m.length
      const tailY = m.y - Math.sin(m.angle) * m.length

      const grad = ctx!.createLinearGradient(m.x, m.y, tailX, tailY)
      grad.addColorStop(0, `rgba(255, 255, 255, ${alpha})`)
      grad.addColorStop(0.3, `rgba(200, 220, 255, ${alpha * 0.5})`)
      grad.addColorStop(1, 'rgba(200, 220, 255, 0)')

      ctx!.beginPath()
      ctx!.moveTo(tailX, tailY)
      ctx!.lineTo(m.x, m.y)
      ctx!.strokeStyle = grad
      ctx!.lineWidth = m.thickness
      ctx!.lineCap = 'round'
      ctx!.stroke()

      ctx!.beginPath()
      ctx!.arc(m.x, m.y, m.thickness + 1, 0, Math.PI * 2)
      ctx!.fillStyle = `rgba(255, 255, 255, ${alpha * 0.8})`
      ctx!.fill()

      return true
    })
  }

  function drawPlexus() {
    if (!ctx) return

    const primaryColor = '14, 165, 233'
    const accentColor = '56, 189, 248'

    interface LineSegment {
      x1: number
      y1: number
      x2: number
      y2: number
    }

    for (const node of plexusNodes) {
      node.x += node.vx
      node.y += node.vy

      const pad = 20
      if (node.x < -pad) node.x = width + pad
      if (node.x > width + pad) node.x = -pad
      if (node.y < -pad) node.y = height + pad
      if (node.y > height + pad) node.y = -pad

      let force = 0

      if (mouse.active) {
        const dx = mouse.x - node.x
        const dy = mouse.y - node.y
        const distSq = dx * dx + dy * dy
        const activeRadius = 180
        const activeRadiusSq = 32400

        if (distSq < activeRadiusSq) {
          const dist = Math.sqrt(distSq)
          force = (activeRadius - dist) / activeRadius

          if (dist > 28) {
            node.x += (dx / dist) * force * 0.38
            node.y += (dy / dist) * force * 0.38
          } else {
            const pushForce = (28 - dist) / 28
            node.x -= (dx / dist) * pushForce * 0.48
            node.y -= (dy / dist) * pushForce * 0.48
          }
          node.radius = node.baseRadius + force * 1.6
        } else if (node.radius > node.baseRadius) {
          node.radius -= 0.05
        }
      } else if (node.radius > node.baseRadius) {
        node.radius -= 0.05
      }

      if (force > 0.05) {
        ctx.beginPath()
        ctx.arc(node.x, node.y, node.radius * 2.3, 0, Math.PI * 2)
        ctx.strokeStyle = `rgba(${accentColor}, ${force * 0.16})`
        ctx.lineWidth = 0.8
        ctx.stroke()
      }

      ctx.beginPath()
      ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(${primaryColor}, ${node.opacity})`
      ctx.fill()
    }

    const b1: LineSegment[] = []
    const b2: LineSegment[] = []
    const b3: LineSegment[] = []
    const b4: LineSegment[] = []

    const maxLinkDistSq = 19600
    const d1Sq = 1225
    const d2Sq = 4900
    const d3Sq = 11025

    for (let i = 0; i < plexusNodes.length; i++) {
      const n1 = plexusNodes[i]

      for (let j = i + 1; j < plexusNodes.length; j++) {
        const n2 = plexusNodes[j]
        const dx = n1.x - n2.x
        const dy = n1.y - n2.y
        const distSq = dx * dx + dy * dy

        if (distSq < maxLinkDistSq) {
          if (distSq < d1Sq) {
            b1.push({ x1: n1.x, y1: n1.y, x2: n2.x, y2: n2.y })
          } else if (distSq < d2Sq) {
            b2.push({ x1: n1.x, y1: n1.y, x2: n2.x, y2: n2.y })
          } else if (distSq < d3Sq) {
            b3.push({ x1: n1.x, y1: n1.y, x2: n2.x, y2: n2.y })
          } else {
            b4.push({ x1: n1.x, y1: n1.y, x2: n2.x, y2: n2.y })
          }
        }
      }
    }

    const drawBucket = (lines: LineSegment[], colorStr: string, w: number) => {
      if (lines.length === 0) return
      ctx!.beginPath()
      ctx!.strokeStyle = colorStr
      ctx!.lineWidth = w
      for (const line of lines) {
        ctx!.moveTo(line.x1, line.y1)
        ctx!.lineTo(line.x2, line.y2)
      }
      ctx!.stroke()
    }

    drawBucket(b1, `rgba(${primaryColor}, 0.22)`, 0.95)
    drawBucket(b2, `rgba(${primaryColor}, 0.14)`, 0.7)
    drawBucket(b3, `rgba(${primaryColor}, 0.08)`, 0.5)
    drawBucket(b4, `rgba(${primaryColor}, 0.04)`, 0.3)

    if (mouse.active) {
      const mb1: LineSegment[] = []
      const mb2: LineSegment[] = []
      const mb3: LineSegment[] = []

      const mouseLinkDistSq = 32400
      const md1Sq = 3600
      const md2Sq = 14400

      for (let i = 0; i < plexusNodes.length; i++) {
        const n1 = plexusNodes[i]
        const dx = mouse.x - n1.x
        const dy = mouse.y - n1.y
        const distSq = dx * dx + dy * dy

        if (distSq < mouseLinkDistSq) {
          if (distSq < md1Sq) {
            mb1.push({ x1: n1.x, y1: n1.y, x2: mouse.x, y2: mouse.y })
          } else if (distSq < md2Sq) {
            mb2.push({ x1: n1.x, y1: n1.y, x2: mouse.x, y2: mouse.y })
          } else {
            mb3.push({ x1: n1.x, y1: n1.y, x2: mouse.x, y2: mouse.y })
          }
        }
      }

      drawBucket(mb1, `rgba(${accentColor}, 0.35)`, 1.1)
      drawBucket(mb2, `rgba(${accentColor}, 0.20)`, 0.75)
      drawBucket(mb3, `rgba(${accentColor}, 0.08)`, 0.45)
    }
  }

  function animate(time: number) {
    if (!ctx) return
    ctx.clearRect(0, 0, width, height)

    const isBlack = document.documentElement.dataset.theme === 'black'

    if (isBlack) {
      drawStars(time)
      if (Math.random() < 0.06) spawnMeteor()
      drawMeteors()
    } else {
      drawPlexus()
    }

    animationId = requestAnimationFrame(animate)
  }

  function handleResize() {
    resize()
    initStars()
    initPlexus()
  }

  const handleMouseMove = (e: MouseEvent) => {
    mouse.x = e.clientX
    mouse.y = e.clientY
    mouse.active = true
  }

  const handleMouseLeave = () => {
    mouse.x = -1000
    mouse.y = -1000
    mouse.active = false
  }

  onMounted(() => {
    initCanvas()
    animationId = requestAnimationFrame(animate)
    window.addEventListener('resize', handleResize)
    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseleave', handleMouseLeave)
  })

  onUnmounted(() => {
    cancelAnimationFrame(animationId)
    window.removeEventListener('resize', handleResize)
    window.removeEventListener('mousemove', handleMouseMove)
    window.removeEventListener('mouseleave', handleMouseLeave)
  })
}
