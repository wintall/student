import * as faceapi from '@vladmandic/face-api'

const MODEL_URL = '/models'

export interface FaceDetectionResult {
  success: boolean
  message: string
  featureVector?: number[]
  confidence?: number
}

export async function initFaceApi(): Promise<void> {
  await faceapi.loadSsdMobilenetv1Model(MODEL_URL)
  await faceapi.loadFaceLandmarkModel(MODEL_URL)
  await faceapi.loadFaceRecognitionModel(MODEL_URL)
}

export async function detectAndExtract(
  image: HTMLImageElement | HTMLVideoElement
): Promise<FaceDetectionResult> {
  try {
    const detections = await faceapi.detectAllFaces(image).withFaceLandmarks().withFaceDescriptors()

    if (detections.length === 0) {
      return { success: false, message: '未检测到人脸' }
    }

    if (detections.length > 1) {
      return { success: false, message: '检测到多张人脸，请确保只有一个人在镜头前' }
    }

    const descriptor = detections[0].descriptor
    const featureVector = Array.from(descriptor)

    return {
      success: true,
      message: '人脸检测成功',
      featureVector,
      confidence: 1.0,
    }
  } catch (error) {
    console.error('人脸检测失败:', error)
    return { success: false, message: '人脸检测失败，请重试' }
  }
}