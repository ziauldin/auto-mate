document.addEventListener("DOMContentLoaded", () => {
  // Initialize charts on dashboard
  if (document.getElementById("activityChart")) {
    initCharts()
  }

  // Initialize search functionality
  if (document.getElementById("userSearch")) {
    initUserSearch()
  }

  if (document.getElementById("sessionSearch")) {
    initSessionSearch()
  }

  // Initialize tooltips
  var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
  var tooltipList = tooltipTriggerList.map((tooltipTriggerEl) => new window.bootstrap.Tooltip(tooltipTriggerEl))

  // Auto-refresh dashboard every 30 seconds
  if (window.location.pathname === "/admin" || window.location.pathname === "/admin/") {
    setInterval(() => {
      if (document.visibilityState === "visible") {
        updateDashboardStats()
      }
    }, 30000)
  }
})

function initCharts() {
  // Activity Chart
  const activityCtx = document.getElementById("activityChart")
  if (activityCtx) {
    const activityChart = new Chart(activityCtx.getContext("2d"), {
      type: "line",
      data: {
        labels: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        datasets: [
          {
            label: "Sessions",
            data: [45, 52, 38, 65, 59, 43, 48],
            backgroundColor: "rgba(79, 70, 229, 0.1)",
            borderColor: "rgba(79, 70, 229, 1)",
            borderWidth: 3,
            fill: true,
            tension: 0.4,
            pointBackgroundColor: "rgba(79, 70, 229, 1)",
            pointBorderColor: "#fff",
            pointBorderWidth: 2,
            pointRadius: 6,
            pointHoverRadius: 8,
          },
          {
            label: "Messages",
            data: [180, 208, 152, 260, 236, 172, 192],
            backgroundColor: "rgba(34, 197, 94, 0.1)",
            borderColor: "rgba(34, 197, 94, 1)",
            borderWidth: 3,
            fill: true,
            tension: 0.4,
            pointBackgroundColor: "rgba(34, 197, 94, 1)",
            pointBorderColor: "#fff",
            pointBorderWidth: 2,
            pointRadius: 6,
            pointHoverRadius: 8,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "top",
            labels: {
              usePointStyle: true,
              padding: 20,
            },
          },
          tooltip: {
            mode: "index",
            intersect: false,
            backgroundColor: "rgba(0, 0, 0, 0.8)",
            titleColor: "#fff",
            bodyColor: "#fff",
            borderColor: "rgba(79, 70, 229, 1)",
            borderWidth: 1,
          },
        },
        scales: {
          x: {
            grid: {
              display: false,
            },
            ticks: {
              color: "#64748b",
            },
          },
          y: {
            beginAtZero: true,
            grid: {
              color: "rgba(203, 213, 225, 0.5)",
            },
            ticks: {
              color: "#64748b",
            },
          },
        },
        interaction: {
          mode: "nearest",
          axis: "x",
          intersect: false,
        },
      },
    })
  }

  // Models Chart
  const modelsCtx = document.getElementById("modelsChart")
  if (modelsCtx) {
    const modelsChart = new Chart(modelsCtx.getContext("2d"), {
      type: "doughnut",
      data: {
        labels: ["Toyota", "Honda", "Ford", "BMW", "Mercedes", "Others"],
        datasets: [
          {
            data: [28, 22, 18, 12, 10, 10],
            backgroundColor: [
              "rgba(239, 68, 68, 0.8)",
              "rgba(34, 197, 94, 0.8)",
              "rgba(59, 130, 246, 0.8)",
              "rgba(168, 85, 247, 0.8)",
              "rgba(245, 158, 11, 0.8)",
              "rgba(107, 114, 128, 0.8)",
            ],
            borderColor: [
              "rgba(239, 68, 68, 1)",
              "rgba(34, 197, 94, 1)",
              "rgba(59, 130, 246, 1)",
              "rgba(168, 85, 247, 1)",
              "rgba(245, 158, 11, 1)",
              "rgba(107, 114, 128, 1)",
            ],
            borderWidth: 2,
            hoverOffset: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "bottom",
            labels: {
              usePointStyle: true,
              padding: 15,
              generateLabels: (chart) => {
                const data = chart.data
                if (data.labels.length && data.datasets.length) {
                  return data.labels.map((label, i) => {
                    const dataset = data.datasets[0]
                    const value = dataset.data[i]
                    const total = dataset.data.reduce((a, b) => a + b, 0)
                    const percentage = ((value / total) * 100).toFixed(1)
                    return {
                      text: `${label} (${percentage}%)`,
                      fillStyle: dataset.backgroundColor[i],
                      strokeStyle: dataset.borderColor[i],
                      lineWidth: dataset.borderWidth,
                      pointStyle: "circle",
                    }
                  })
                }
                return []
              },
            },
          },
          tooltip: {
            callbacks: {
              label: (context) => {
                const label = context.label || ""
                const value = context.parsed
                const total = context.dataset.data.reduce((a, b) => a + b, 0)
                const percentage = ((value / total) * 100).toFixed(1)
                return `${label}: ${value} (${percentage}%)`
              },
            },
          },
        },
      },
    })
  }
}

function initUserSearch() {
  const searchInput = document.getElementById("userSearch")
  if (!searchInput) return

  let searchTimeout
  searchInput.addEventListener("input", function () {
    clearTimeout(searchTimeout)
    searchTimeout = setTimeout(() => {
      const searchTerm = this.value.toLowerCase()
      const rows = document.querySelectorAll("#usersTable tbody tr")
      let visibleCount = 0

      rows.forEach((row) => {
        const text = row.textContent.toLowerCase()
        const isVisible = text.includes(searchTerm)
        row.style.display = isVisible ? "" : "none"
        if (isVisible) visibleCount++
      })

      // Update showing count
      const showingCountEl = document.getElementById("showingCount")
      if (showingCountEl) {
        showingCountEl.textContent = visibleCount
      }
    }, 300)
  })

  // Add filters functionality
  const statusFilter = document.getElementById("statusFilter")
  const sortBy = document.getElementById("sortBy")

  if (statusFilter) {
    statusFilter.addEventListener("change", applyFilters)
  }
  if (sortBy) {
    sortBy.addEventListener("change", applyFilters)
  }
}

function initSessionSearch() {
  const searchInput = document.getElementById("sessionSearch")
  if (!searchInput) return

  let searchTimeout
  searchInput.addEventListener("input", function () {
    clearTimeout(searchTimeout)
    searchTimeout = setTimeout(() => {
      const searchTerm = this.value.toLowerCase()
      const rows = document.querySelectorAll("#sessionsTable tbody tr")
      let visibleCount = 0

      rows.forEach((row) => {
        const text = row.textContent.toLowerCase()
        const isVisible = text.includes(searchTerm)
        row.style.display = isVisible ? "" : "none"
        if (isVisible) visibleCount++
      })

      // Update session count
      const sessionCountEl = document.getElementById("sessionCount")
      if (sessionCountEl) {
        sessionCountEl.textContent = visibleCount
      }
    }, 300)
  })

  // Add filters functionality
  const manufacturerFilter = document.getElementById("manufacturerFilter")
  const dateFilter = document.getElementById("dateFilter")
  const statusFilter = document.getElementById("statusFilter")

  if (manufacturerFilter) {
    manufacturerFilter.addEventListener("change", applySessionFilters)
  }
  if (dateFilter) {
    dateFilter.addEventListener("change", applySessionFilters)
  }
  if (statusFilter) {
    statusFilter.addEventListener("change", applySessionFilters)
  }
}

function applyFilters() {
  const statusFilter = document.getElementById("statusFilter")?.value || ""
  const sortBy = document.getElementById("sortBy")?.value || ""
  const searchTerm = document.getElementById("userSearch")?.value.toLowerCase() || ""

  const rows = Array.from(document.querySelectorAll("#usersTable tbody tr"))
  const visibleRows = []

  rows.forEach((row) => {
    let isVisible = true

    // Apply search filter
    if (searchTerm && !row.textContent.toLowerCase().includes(searchTerm)) {
      isVisible = false
    }

    // Apply status filter
    if (statusFilter) {
      const statusBadge = row.querySelector(".badge")
      const rowStatus = statusBadge ? statusBadge.textContent.toLowerCase() : ""
      if (statusFilter === "active" && rowStatus !== "active") isVisible = false
      if (statusFilter === "inactive" && rowStatus !== "inactive") isVisible = false
      if (statusFilter === "banned" && rowStatus !== "banned") isVisible = false
    }

    row.style.display = isVisible ? "" : "none"
    if (isVisible) visibleRows.push(row)
  })

  // Apply sorting
  if (sortBy && visibleRows.length > 0) {
    const tbody = document.querySelector("#usersTable tbody")
    visibleRows.sort((a, b) => {
      let aValue, bValue

      switch (sortBy) {
        case "session_count":
          aValue = Number.parseInt(a.cells[3].textContent) || 0
          bValue = Number.parseInt(b.cells[3].textContent) || 0
          return bValue - aValue // Descending
        case "user_id":
          aValue = a.cells[1].textContent.toLowerCase()
          bValue = b.cells[1].textContent.toLowerCase()
          return aValue.localeCompare(bValue) // Ascending
        case "last_active":
        default:
          // Sort by last active (assuming it's in a parseable format)
          const aDate = a.cells[4].textContent === "Never" ? new Date(0) : new Date(a.cells[4].textContent)
          const bDate = b.cells[4].textContent === "Never" ? new Date(0) : new Date(b.cells[4].textContent)
          return bDate - aDate // Most recent first
      }
    })

    // Re-append sorted rows
    visibleRows.forEach((row) => tbody.appendChild(row))
  }

  // Update showing count
  const showingCountEl = document.getElementById("showingCount")
  if (showingCountEl) {
    showingCountEl.textContent = visibleRows.length
  }
}

function applySessionFilters() {
  const manufacturerFilter = document.getElementById("manufacturerFilter")?.value || ""
  const dateFilter = document.getElementById("dateFilter")?.value || ""
  const statusFilter = document.getElementById("statusFilter")?.value || ""
  const searchTerm = document.getElementById("sessionSearch")?.value.toLowerCase() || ""

  const rows = document.querySelectorAll("#sessionsTable tbody tr")
  let visibleCount = 0

  rows.forEach((row) => {
    let isVisible = true

    // Apply search filter
    if (searchTerm && !row.textContent.toLowerCase().includes(searchTerm)) {
      isVisible = false
    }

    // Apply manufacturer filter
    if (manufacturerFilter) {
      const vehicleCell = row.cells[3] // Vehicle column
      if (!vehicleCell.textContent.includes(manufacturerFilter)) {
        isVisible = false
      }
    }

    // Apply date filter
    if (dateFilter) {
  const createdCell = row.cells[7] // Created column
  const createdDate = new Date(createdCell.textContent)
  const now = new Date()

  switch (dateFilter) {
    case "today":
      if (createdDate.toDateString() !== now.toDateString()) {
        isVisible = false
      }
      break
    case "week":
      const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
      if (createdDate < weekAgo) {
        isVisible = false
      }
      break
    case "month":
      const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
      if (createdDate < monthAgo) {
        isVisible = false
      }
      break
  }
}

    // Apply status filter
    if (statusFilter) {
      const statusBadge = row.querySelector(".badge")
      const rowStatus = statusBadge ? statusBadge.textContent.toLowerCase() : ""
      if (statusFilter !== rowStatus) {
        isVisible = false
      }
    }

    row.style.display = isVisible ? "" : "none"
    if (isVisible) visibleCount++
  })

  // Update session count
  const sessionCountEl = document.getElementById("sessionCount")
  if (sessionCountEl) {
    sessionCountEl.textContent = visibleCount
  }
}

function updateDashboardStats() {
  fetch("/admin/api/stats")
    .then((response) => response.json())
    .then((data) => {
      // Update stat cards
      const statCards = document.querySelectorAll(".stat-card .display-4")
      if (statCards[0]) statCards[0].textContent = data.total_users || 0
      if (statCards[1]) statCards[1].textContent = data.total_sessions || 0
      if (statCards[2]) statCards[2].textContent = data.total_messages || 0
      if (statCards[3]) statCards[3].textContent = data.active_today || 0
    })
    .catch((error) => {
      console.error("Error updating dashboard stats:", error)
    })
}

// Utility functions
function showNotification(message, type = "info") {
  const notification = document.createElement("div")
  notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`
  notification.style.cssText = "top: 20px; right: 20px; z-index: 9999; min-width: 300px;"
  notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `

  document.body.appendChild(notification)

  // Auto-remove after 5 seconds
  setTimeout(() => {
    if (notification.parentNode) {
      notification.parentNode.removeChild(notification)
    }
  }, 5000)
}

function formatNumber(num) {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + "M"
  } else if (num >= 1000) {
    return (num / 1000).toFixed(1) + "K"
  }
  return num.toString()
}

function formatDate(dateString) {
  const date = new Date(dateString)
  const now = new Date()
  const diffTime = Math.abs(now - date)
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))

  if (diffDays === 1) {
    return "Yesterday"
  } else if (diffDays < 7) {
    return `${diffDays} days ago`
  } else if (diffDays < 30) {
    const weeks = Math.floor(diffDays / 7)
    return `${weeks} week${weeks > 1 ? "s" : ""} ago`
  } else {
    return date.toLocaleDateString()
  }
}

// Export functions
window.adminUtils = {
  showNotification,
  formatNumber,
  formatDate,
  updateDashboardStats,
}