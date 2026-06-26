export interface GeolocationResult {
  latitude: number
  longitude: number
  city?: string
  error?: string
}

export function getCurrentLocation(timeout: number = 5000): Promise<GeolocationResult> {
  return new Promise((resolve) => {
    if (!navigator.geolocation) {
      resolve({
        latitude: 0,
        longitude: 0,
        error: 'Browser does not support geolocation',
      })
      return
    }

    let settled = false
    let timer: ReturnType<typeof setTimeout> | null = null

    const finish = (result: GeolocationResult) => {
      if (settled) return
      settled = true
      if (timer) {
        clearTimeout(timer)
        timer = null
      }
      resolve(result)
    }

    const success = (position: GeolocationPosition) => {
      finish({
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
      })
    }

    const failure = (error: GeolocationPositionError) => {
      const messages: Record<number, string> = {
        [error.PERMISSION_DENIED]: 'Geolocation permission denied',
        [error.POSITION_UNAVAILABLE]: 'Geolocation unavailable',
        [error.TIMEOUT]: 'Geolocation timed out',
      }

      finish({
        latitude: 0,
        longitude: 0,
        error: messages[error.code] || 'Failed to get geolocation',
      })
    }

    timer = setTimeout(() => {
      finish({
        latitude: 0,
        longitude: 0,
        error: 'Geolocation timed out',
      })
    }, timeout)

    navigator.geolocation.getCurrentPosition(success, failure, {
      enableHighAccuracy: false,
      timeout,
      maximumAge: 300000,
    })
  })
}

export async function getCityByLocation(latitude: number, longitude: number): Promise<string | null> {
  try {
    const response = await fetch(
      `https://restapi.amap.com/v3/geocode/regeo?key=436cc97cb02b3067da8f31c938b1b56a&location=${longitude},${latitude}&output=JSON&radius=1000&extensions=all`
    )
    const data = await response.json()
    if (data.status === '1' && data.regeocode) {
      const addressComponent = data.regeocode.addressComponent
      return addressComponent.city || addressComponent.province || null
    }
    return null
  } catch {
    return null
  }
}
