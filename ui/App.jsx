import { useState } from 'react'
import { BrowserRouter as Router, Routes, Route, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button.jsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Badge } from '@/components/ui/badge.jsx'
import { Progress } from '@/components/ui/progress.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select.jsx'
import { Textarea } from '@/components/ui/textarea.jsx'
import { Slider } from '@/components/ui/slider.jsx'
import { Checkbox } from '@/components/ui/checkbox.jsx'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group.jsx'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.jsx'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar.jsx'
import { 
  Video, 
  Mic, 
  MicOff, 
  VideoOff, 
  Phone, 
  Play, 
  Pause, 
  Code, 
  FileText, 
  Users, 
  BarChart3, 
  CheckCircle, 
  Clock, 
  Star,
  Eye,
  Brain,
  MessageSquare,
  Target,
  Award,
  TrendingUp,
  Filter,
  Search,
  Download,
  Share
} from 'lucide-react'
import { PieChart, Pie, Cell, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, ResponsiveContainer } from 'recharts'
import './App.css'

// Home Page Component
function HomePage() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <h1 className="text-2xl font-bold text-gray-900">AI Interviewer</h1>
              </div>
            </div>
            <nav className="hidden md:block">
              <div className="ml-10 flex items-baseline space-x-4">
                <a href="#" className="text-gray-500 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium">Dashboard</a>
                <a href="#" className="text-gray-500 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium">Interviews</a>
                <a href="#" className="text-gray-500 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium">Subscription</a>
                <Button variant="outline" size="sm">Upgrade</Button>
              </div>
            </nav>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-5xl font-bold text-gray-900 mb-6">
            Transform Your Hiring Process with AI-Powered Interviews
          </h1>
          <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
            Streamline candidate selection through automated AI-driven screening interviews with comprehensive analysis and detailed reporting.
          </p>
          <Button 
            size="lg" 
            className="bg-green-600 hover:bg-green-700 text-white px-8 py-4 text-lg"
            onClick={() => navigate('/job-setup')}
          >
            Start Interview
          </Button>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-16 px-4 sm:px-6 lg:px-8 bg-white">
        <div className="max-w-6xl mx-auto">
          <div className="grid md:grid-cols-3 gap-8">
            <Card className="text-center">
              <CardHeader>
                <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Users className="w-8 h-8 text-green-600" />
                </div>
                <CardTitle>Automated Screening</CardTitle>
              </CardHeader>
              <CardContent>
                <CardDescription>
                  Efficient AI-powered candidate screening with intelligent question generation and automated analysis.
                </CardDescription>
              </CardContent>
            </Card>

            <Card className="text-center">
              <CardHeader>
                <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Video className="w-8 h-8 text-green-600" />
                </div>
                <CardTitle>Video Interviews</CardTitle>
              </CardHeader>
              <CardContent>
                <CardDescription>
                  Comprehensive video interview platform with real-time monitoring and live proctoring capabilities.
                </CardDescription>
              </CardContent>
            </Card>

            <Card className="text-center">
              <CardHeader>
                <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <BarChart3 className="w-8 h-8 text-green-600" />
                </div>
                <CardTitle>Detailed Reports</CardTitle>
              </CardHeader>
              <CardContent>
                <CardDescription>
                  Comprehensive candidate assessment with technical scores, communication analysis, and hiring recommendations.
                </CardDescription>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="py-16 px-4 sm:px-6 lg:px-8 bg-gray-50">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center text-gray-900 mb-12">How It Works</h2>
          <div className="grid md:grid-cols-6 gap-4">
            {[
              { number: 1, title: "Job Setup", desc: "Configure job details and requirements" },
              { number: 2, title: "Upload Description", desc: "Add job description and skills" },
              { number: 3, title: "Interview Process", desc: "5-stage AI-powered interview" },
              { number: 4, title: "Live Proctoring", desc: "Real-time monitoring and analysis" },
              { number: 5, title: "Filter Candidates", desc: "Review and filter results" },
              { number: 6, title: "Detailed Reports", desc: "Comprehensive assessment reports" }
            ].map((step) => (
              <div key={step.number} className="text-center">
                <div className="w-12 h-12 bg-green-600 text-white rounded-full flex items-center justify-center mx-auto mb-4 text-lg font-bold">
                  {step.number}
                </div>
                <h3 className="font-semibold text-gray-900 mb-2">{step.title}</h3>
                <p className="text-sm text-gray-600">{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}

// Job Setup Component
function JobSetup() {
  const navigate = useNavigate()
  const [formData, setFormData] = useState({
    jobTitle: '',
    experience: [4],
    level: '',
    employmentType: '',
    location: '',
    city: ''
  })

  const handleContinue = () => {
    navigate('/job-description')
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        {/* Progress Bar */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-700">Step 1 of 3 - Job Details</span>
          </div>
          <Progress value={33} className="h-2" />
        </div>

        <Card>
          <CardContent className="p-8">
            <div className="grid md:grid-cols-2 gap-8">
              {/* Left Column - Interview Configuration */}
              <div>
                <h3 className="text-lg font-semibold mb-6">Interview Configuration</h3>
                
                <div className="space-y-4">
                  <div>
                    <Label className="text-sm text-gray-600">Interview Type</Label>
                    <p className="font-medium">One-way Interview</p>
                  </div>
                  
                  <div>
                    <Label className="text-sm text-gray-600">Interview Language</Label>
                    <p className="font-medium">English</p>
                  </div>
                  
                  <div>
                    <Label className="text-sm text-gray-600">AI Avatar</Label>
                    <p className="font-medium">Voice</p>
                  </div>
                </div>
              </div>

              {/* Right Column - Job Details */}
              <div>
                <h3 className="text-lg font-semibold mb-6">Job Details</h3>
                
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="jobTitle">Job Title</Label>
                    <Select value={formData.jobTitle} onValueChange={(value) => setFormData({...formData, jobTitle: value})}>
                      <SelectTrigger>
                        <SelectValue placeholder="Sr. React JS Developer" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="sr-react-dev">Sr. React JS Developer</SelectItem>
                        <SelectItem value="frontend-dev">Frontend Developer</SelectItem>
                        <SelectItem value="fullstack-dev">Full Stack Developer</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <Label>Years of Experience: {formData.experience[0]}-{formData.experience[0] + 2} Years</Label>
                    <Slider
                      value={formData.experience}
                      onValueChange={(value) => setFormData({...formData, experience: value})}
                      max={15}
                      min={0}
                      step={1}
                      className="mt-2"
                    />
                  </div>

                  <div>
                    <Label htmlFor="level">Level</Label>
                    <Select value={formData.level} onValueChange={(value) => setFormData({...formData, level: value})}>
                      <SelectTrigger>
                        <SelectValue placeholder="Mid Level" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="junior">Junior Level</SelectItem>
                        <SelectItem value="mid">Mid Level</SelectItem>
                        <SelectItem value="senior">Senior Level</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="employmentType">Employment Type</Label>
                      <Select value={formData.employmentType} onValueChange={(value) => setFormData({...formData, employmentType: value})}>
                        <SelectTrigger>
                          <SelectValue placeholder="Full-Time" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="full-time">Full-Time</SelectItem>
                          <SelectItem value="part-time">Part-Time</SelectItem>
                          <SelectItem value="contract">Contract</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div>
                      <Label htmlFor="workType">Work Type</Label>
                      <Select>
                        <SelectTrigger>
                          <SelectValue placeholder="On-Site" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="onsite">On-Site</SelectItem>
                          <SelectItem value="remote">Remote</SelectItem>
                          <SelectItem value="hybrid">Hybrid</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="location">Country</Label>
                      <Select value={formData.location} onValueChange={(value) => setFormData({...formData, location: value})}>
                        <SelectTrigger>
                          <SelectValue placeholder="India" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="india">India</SelectItem>
                          <SelectItem value="usa">USA</SelectItem>
                          <SelectItem value="uk">UK</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div>
                      <Label htmlFor="city">City</Label>
                      <Select value={formData.city} onValueChange={(value) => setFormData({...formData, city: value})}>
                        <SelectTrigger>
                          <SelectValue placeholder="Jaipur" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="jaipur">Jaipur</SelectItem>
                          <SelectItem value="delhi">Delhi</SelectItem>
                          <SelectItem value="mumbai">Mumbai</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <div>
                    <Label htmlFor="salary">Salary Range (Optional)</Label>
                    <Input placeholder="e.g., $50,000 - $70,000" />
                  </div>
                </div>
              </div>
            </div>

            <div className="flex justify-end mt-8">
              <Button 
                onClick={handleContinue}
                className="bg-green-600 hover:bg-green-700 text-white px-8"
              >
                Continue
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

// Job Description Component
function JobDescription() {
  const navigate = useNavigate()
  const [jobDescription, setJobDescription] = useState(`We are looking for a proficient Sr. React JS Developer with 4-6 years of experience for our team in Jaipur. The role requires expertise in developing user interface components and ensuring they are...`)

  const skills = ['React JS', 'JavaScript', 'DOM Manipulation', 'HTML/CSS', 'Redux']

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        {/* Progress Bar */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-700">Step 2 of 3 - Upload Job Description</span>
          </div>
          <Progress value={66} className="h-2" />
        </div>

        <Card>
          <CardContent className="p-8">
            <div className="grid md:grid-cols-2 gap-8">
              {/* Left Column - Interview Configuration */}
              <div>
                <h3 className="text-lg font-semibold mb-6">Interview Configuration</h3>
                
                <div className="space-y-4">
                  <div>
                    <Label className="text-sm text-gray-600">Interview Type</Label>
                    <p className="font-medium">One-way Interview</p>
                  </div>
                  
                  <div>
                    <Label className="text-sm text-gray-600">Interview Language</Label>
                    <p className="font-medium">English</p>
                  </div>
                  
                  <div>
                    <Label className="text-sm text-gray-600">AI Avatar</Label>
                    <p className="font-medium">Voice</p>
                  </div>
                </div>
              </div>

              {/* Right Column - Job Description */}
              <div>
                <div className="space-y-6">
                  <div>
                    <Label htmlFor="jobDescription">Job Description</Label>
                    <Textarea 
                      value={jobDescription}
                      onChange={(e) => setJobDescription(e.target.value)}
                      className="min-h-32 mt-2"
                      placeholder="Enter job description..."
                    />
                    <Button variant="link" className="p-0 h-auto text-blue-600">Read More</Button>
                  </div>

                  <div>
                    <Label>Skills required</Label>
                    <div className="flex flex-wrap gap-2 mt-2">
                      {skills.map((skill) => (
                        <Badge key={skill} variant="secondary">{skill}</Badge>
                      ))}
                      <Badge variant="outline">...</Badge>
                    </div>
                  </div>

                  <div>
                    <Label>Pre-Interview Screening</Label>
                    <div className="mt-2 p-4 border rounded-lg">
                      <p className="text-sm mb-3">1. Total work experience in react js</p>
                      <RadioGroup defaultValue="minimum">
                        <div className="flex items-center space-x-2">
                          <RadioGroupItem value="minimum" id="minimum" />
                          <Label htmlFor="minimum">3 (Minimum)</Label>
                        </div>
                        <div className="flex items-center space-x-2">
                          <RadioGroupItem value="advanced" id="advanced" />
                          <Label htmlFor="advanced">Beginner to Advanced</Label>
                        </div>
                      </RadioGroup>
                    </div>
                  </div>

                  <div>
                    <Label>Notification</Label>
                    <div className="mt-2 space-y-2">
                      <div className="flex items-center space-x-2">
                        <Checkbox id="email" defaultChecked />
                        <Label htmlFor="email">Email</Label>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Checkbox id="whatsapp" />
                        <Label htmlFor="whatsapp">WhatsApp</Label>
                      </div>
                    </div>
                  </div>

                  <div>
                    <Label>Added Questions</Label>
                    <div className="mt-2 p-4 border rounded-lg">
                      <div className="flex justify-between items-center mb-3">
                        <span className="text-sm font-medium">5 Questions</span>
                        <span className="text-sm text-gray-600">10 mins</span>
                      </div>
                      <div className="text-sm">
                        <p className="mb-2">Question 1:</p>
                        <p className="text-gray-600 mb-3">Can you briefly introduce yourself and highlight your key skills?</p>
                        <div className="flex gap-2">
                          <Badge variant="outline" className="text-xs">General</Badge>
                          <Badge variant="outline" className="text-xs">Video</Badge>
                          <Badge variant="outline" className="text-xs">Moderate</Badge>
                          <Badge variant="outline" className="text-xs">Hiring AI</Badge>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex justify-end mt-8">
              <Button 
                onClick={() => navigate('/interview')}
                className="bg-green-600 hover:bg-green-700 text-white px-8"
              >
                Start Interview
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

// Interview Interface Component
function InterviewInterface() {
  const navigate = useNavigate()
  const [currentStage, setCurrentStage] = useState(1)
  const [isRecording, setIsRecording] = useState(true)
  const [isMuted, setIsMuted] = useState(false)
  const [isVideoOn, setIsVideoOn] = useState(true)
  const [timer, setTimer] = useState('07:06')

  const stages = [
    'Introduction',
    'Technical Questions', 
    'Coding Challenge',
    'Feedback',
    'Behavioral Questions',
    'Conclusion'
  ]

  const currentQuestion = "Can you explain the concept of indexing in MongoDB and why it's essential?"

  return (
    <div className="min-h-screen bg-gray-900">
      {/* Header */}
      <header className="bg-gray-800 text-white p-4">
        <div className="flex justify-between items-center">
          <h1 className="text-xl font-bold">AI Interviewer</h1>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-green-500 rounded-full"></div>
              <span className="text-sm">Recording</span>
            </div>
            <div className="text-sm">Stage {currentStage}/6: {stages[currentStage - 1]}</div>
          </div>
        </div>
      </header>

      {/* Main Interview Area */}
      <div className="flex h-[calc(100vh-80px)]">
        {/* Video Feed */}
        <div className="w-1/2 bg-gray-800 relative">
          <div className="absolute inset-4 bg-gray-700 rounded-lg overflow-hidden">
            <div className="w-full h-full bg-gradient-to-br from-blue-900 to-gray-800 flex items-center justify-center">
              <div className="text-center text-white">
                <div className="w-24 h-24 bg-gray-600 rounded-full mx-auto mb-4 flex items-center justify-center">
                  <Video className="w-12 h-12" />
                </div>
                <p>Candidate Video Feed</p>
              </div>
            </div>
          </div>
        </div>

        {/* Question/Content Panel */}
        <div className="w-1/2 bg-white p-8">
          <div className="h-full flex flex-col">
            {/* Timer */}
            <div className="text-center mb-6">
              <div className="text-2xl font-mono text-gray-600">{timer} - 02:13</div>
            </div>

            {/* Question */}
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center max-w-md">
                <h2 className="text-2xl font-semibold text-gray-900 mb-4">
                  {currentQuestion}
                </h2>
                {currentStage === 3 && (
                  <div className="mt-8">
                    <Button 
                      onClick={() => navigate('/coding-challenge')}
                      className="bg-green-600 hover:bg-green-700 text-white"
                    >
                      <Code className="w-4 h-4 mr-2" />
                      Open Code Editor
                    </Button>
                  </div>
                )}
              </div>
            </div>

            {/* Stage Navigation */}
            <div className="flex justify-between items-center">
              <Button 
                variant="outline" 
                onClick={() => setCurrentStage(Math.max(1, currentStage - 1))}
                disabled={currentStage === 1}
              >
                Previous
              </Button>
              <div className="flex gap-2">
                {stages.map((_, index) => (
                  <div 
                    key={index}
                    className={`w-3 h-3 rounded-full ${
                      index + 1 === currentStage ? 'bg-green-600' : 
                      index + 1 < currentStage ? 'bg-green-400' : 'bg-gray-300'
                    }`}
                  />
                ))}
              </div>
              <Button 
                onClick={() => {
                  if (currentStage < 6) {
                    setCurrentStage(currentStage + 1)
                  } else {
                    navigate('/report')
                  }
                }}
                className="bg-green-600 hover:bg-green-700 text-white"
              >
                {currentStage === 6 ? 'Finish' : 'Next'}
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Control Bar */}
      <div className="bg-gray-800 p-4">
        <div className="flex justify-center gap-4">
          <Button
            variant={isMuted ? "destructive" : "secondary"}
            size="lg"
            className="rounded-full w-12 h-12"
            onClick={() => setIsMuted(!isMuted)}
          >
            {isMuted ? <MicOff className="w-6 h-6" /> : <Mic className="w-6 h-6" />}
          </Button>
          
          <Button
            variant={!isVideoOn ? "destructive" : "secondary"}
            size="lg"
            className="rounded-full w-12 h-12"
            onClick={() => setIsVideoOn(!isVideoOn)}
          >
            {!isVideoOn ? <VideoOff className="w-6 h-6" /> : <Video className="w-6 h-6" />}
          </Button>
          
          <Button
            variant="destructive"
            size="lg"
            className="rounded-full w-12 h-12"
            onClick={() => navigate('/report')}
          >
            <Phone className="w-6 h-6" />
          </Button>
        </div>
      </div>
    </div>
  )
}

// Coding Challenge Component
function CodingChallenge() {
  const navigate = useNavigate()
  const [code, setCode] = useState(`function twoSum(nums, target) {
    // Your solution here
    
}`)

  return (
    <div className="min-h-screen bg-gray-900">
      {/* Header */}
      <header className="bg-gray-800 text-white p-4">
        <div className="flex justify-between items-center">
          <h1 className="text-xl font-bold">AI Interviewer - Coding Challenge</h1>
          <div className="flex items-center gap-4">
            <div className="text-sm">Time: 79:93</div>
            <div className="text-sm">17:3</div>
          </div>
        </div>
      </header>

      <div className="flex h-[calc(100vh-80px)]">
        {/* Video Feed - Smaller */}
        <div className="w-1/4 bg-gray-800 p-4">
          <div className="bg-gray-700 rounded-lg h-48 mb-4 overflow-hidden">
            <div className="w-full h-full bg-gradient-to-br from-blue-900 to-gray-800 flex items-center justify-center">
              <div className="text-center text-white">
                <div className="w-16 h-16 bg-gray-600 rounded-full mx-auto mb-2 flex items-center justify-center">
                  <Video className="w-8 h-8" />
                </div>
                <p className="text-sm">Candidate</p>
              </div>
            </div>
          </div>
          
          {/* Controls */}
          <div className="flex justify-center gap-2">
            <Button variant="secondary" size="sm" className="rounded-full">
              <Mic className="w-4 h-4" />
            </Button>
            <Button variant="secondary" size="sm" className="rounded-full">
              <Video className="w-4 h-4" />
            </Button>
            <Button variant="secondary" size="sm" className="rounded-full">
              <MessageSquare className="w-4 h-4" />
            </Button>
            <Button variant="destructive" size="sm" className="rounded-full">
              <Phone className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Code Editor Area */}
        <div className="flex-1 bg-gray-900 text-white">
          {/* Problem Statement */}
          <div className="p-6 border-b border-gray-700">
            <h2 className="text-xl font-bold mb-4">Two Sum</h2>
            <p className="text-gray-300 mb-4">
              Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.
            </p>
            <div className="space-y-2 text-sm text-gray-400">
              <p>• You may assume that each input would have exactly one solution, and you may not use the same element twice.</p>
              <p>• You can return the answer in any order.</p>
            </div>
          </div>

          {/* Code Editor */}
          <div className="flex-1 p-6">
            <div className="bg-gray-800 rounded-lg p-4 font-mono text-sm">
              <div className="flex">
                <div className="text-gray-500 pr-4 select-none">
                  {Array.from({length: 10}, (_, i) => (
                    <div key={i}>{i + 1}</div>
                  ))}
                </div>
                <div className="flex-1">
                  <div className="text-purple-400">function <span className="text-blue-400">twoSum</span>(<span className="text-orange-400">nums</span>, <span className="text-orange-400">target</span>) {'{'}</div>
                  <div className="ml-4 text-gray-300">// Your solution here</div>
                  <div className="ml-4"></div>
                  <div className="text-purple-400">{'}'}</div>
                </div>
              </div>
            </div>

            {/* Test Cases */}
            <div className="mt-6">
              <h3 className="text-lg font-semibold mb-3">Test Cases</h3>
              <div className="bg-gray-800 rounded-lg p-4 text-sm">
                <div className="mb-2">
                  <span className="text-gray-400">Input:</span> nums = [2,7,11,15], target = 9
                </div>
                <div className="mb-4">
                  <span className="text-gray-400">Output:</span> [0,1]
                </div>
                <div className="mb-2">
                  <span className="text-gray-400">Input:</span> nums = [3,2,4], target = 6
                </div>
                <div>
                  <span className="text-gray-400">Output:</span> [1,2]
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex gap-4 mt-6">
              <Button className="bg-green-600 hover:bg-green-700">
                Run Code
              </Button>
              <Button variant="outline" className="text-white border-gray-600">
                Submit
              </Button>
              <Button 
                variant="outline" 
                className="text-white border-gray-600 ml-auto"
                onClick={() => navigate('/interview')}
              >
                Back to Interview
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// Detailed Report Component
function DetailedReport() {
  const navigate = useNavigate()
  
  const technicalData = [
    { name: 'Correct', value: 33, fill: '#ef4444' },
    { name: 'Remaining', value: 67, fill: '#f3f4f6' }
  ]

  const communicationData = [
    { subject: 'Pronunciation', A: 80, fullMark: 100 },
    { subject: 'Fluency', A: 70, fullMark: 100 },
    { subject: 'Grammar', A: 85, fullMark: 100 },
    { subject: 'Vocabulary', A: 75, fullMark: 100 }
  ]

  const skillRatings = [
    { skill: 'Node.js', rating: 1.3, total: 5 },
    { skill: 'JavaScript', rating: 0.3, total: 5 },
    { skill: 'Express.js', rating: 0.7, total: 5 },
    { skill: 'MongoDB', rating: 1.0, total: 5 },
    { skill: 'SQL', rating: 0.3, total: 5 }
  ]

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-6xl mx-auto px-4">
        {/* Header */}
        <Card className="mb-8">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <Avatar className="w-16 h-16">
                  <AvatarImage src="/placeholder-avatar.jpg" />
                  <AvatarFallback>NR</AvatarFallback>
                </Avatar>
                <div>
                  <h1 className="text-2xl font-bold">Narayanan Raman</h1>
                  <div className="text-sm text-gray-600 space-x-4">
                    <span>24 Apr 2025</span>
                    <span>10m 22s</span>
                    <span>Chennai</span>
                  </div>
                </div>
              </div>
              <div className="text-center">
                <div className="text-sm text-gray-600 mb-1">OVERALL SCORE</div>
                <div className="text-4xl font-bold text-green-600">66%</div>
              </div>
            </div>

            {/* Candidate Details */}
            <div className="grid md:grid-cols-4 gap-6 mt-6 pt-6 border-t">
              <div>
                <div className="text-sm text-gray-600">Experience</div>
                <div className="font-semibold">2 years & 4 months</div>
              </div>
              <div>
                <div className="text-sm text-gray-600">Current Salary</div>
                <div className="font-semibold">$3000</div>
              </div>
              <div>
                <div className="text-sm text-gray-600">Expected Salary</div>
                <div className="font-semibold">$5000</div>
              </div>
              <div>
                <div className="text-sm text-gray-600">Joining Date</div>
                <div className="font-semibold">30 Apr 2025</div>
              </div>
            </div>

            <div className="mt-4">
              <div className="text-sm text-gray-600">Candidate Feedback</div>
              <div className="flex items-center gap-1">
                {[1,2,3,4,5].map((star) => (
                  <Star key={star} className={`w-4 h-4 ${star <= 4 ? 'fill-yellow-400 text-yellow-400' : 'text-gray-300'}`} />
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Main Content */}
        <div className="grid md:grid-cols-2 gap-8">
          {/* Left Column */}
          <div className="space-y-6">
            {/* Technical Score */}
            <Card>
              <CardHeader>
                <CardTitle>Technical Score</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-center mb-4">
                  <div className="relative w-32 h-32">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={technicalData}
                          cx="50%"
                          cy="50%"
                          innerRadius={40}
                          outerRadius={60}
                          startAngle={90}
                          endAngle={450}
                          dataKey="value"
                        >
                          {technicalData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.fill} />
                          ))}
                        </Pie>
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <div className="text-center">
                        <div className="text-2xl font-bold text-red-500">33%</div>
                      </div>
                    </div>
                  </div>
                </div>
                <div className="text-center text-sm text-gray-600">7 Questions</div>
              </CardContent>
            </Card>

            {/* Communication Score */}
            <Card>
              <CardHeader>
                <CardTitle>Communication Score</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-48">
                  <ResponsiveContainer width="100%" height="100%">
                    <RadarChart data={communicationData}>
                      <PolarGrid />
                      <PolarAngleAxis dataKey="subject" />
                      <PolarRadiusAxis angle={90} domain={[0, 100]} />
                      <Radar
                        name="Score"
                        dataKey="A"
                        stroke="#10b981"
                        fill="#10b981"
                        fillOpacity={0.3}
                      />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
                <div className="text-center mt-4">
                  <Badge className="bg-blue-100 text-blue-800">GOOD</Badge>
                </div>
              </CardContent>
            </Card>

            {/* Interview Intelligence */}
            <Card>
              <CardHeader>
                <CardTitle>Interview Intelligence</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-3 gap-4 text-center">
                  <div>
                    <Badge variant="secondary" className="mb-2">Integrity Signals</Badge>
                  </div>
                  <div>
                    <Badge variant="secondary" className="mb-2">Engagement Vibes</Badge>
                  </div>
                  <div>
                    <Badge variant="secondary" className="mb-2">Cognitive Insights</Badge>
                  </div>
                </div>
                
                <div className="mt-4 space-y-2 text-sm">
                  <div className="flex justify-between items-center">
                    <span>Tab Changes</span>
                    <CheckCircle className="w-4 h-4 text-green-500" />
                  </div>
                  <div className="flex justify-between items-center">
                    <span>Multiple faces detected</span>
                    <CheckCircle className="w-4 h-4 text-green-500" />
                  </div>
                  <div className="flex justify-between items-center">
                    <span>Face out of view</span>
                    <CheckCircle className="w-4 h-4 text-green-500" />
                  </div>
                  <div className="flex justify-between items-center">
                    <span>Eye gaze tracking</span>
                    <CheckCircle className="w-4 h-4 text-green-500" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Right Column */}
          <div className="space-y-6">
            {/* AI Summary */}
            <Card>
              <CardHeader>
                <CardTitle>AI Summary</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2 text-sm">
                  <li>• Candidate demonstrates basic understanding of Node.js, is event-driven architecture and its benefits for asynchronous operations.</li>
                  <li>• Shows familiarity with JavaScript concepts like closures, but explanations lack clarity and depth.</li>
                  <li>• Communicates technical ideas with some hesitation, indicating potential gaps in confidence or experience.</li>
                  <li>• Overall performance suggests a junior-level candidate who may benefit from additional training and mentorship.</li>
                </ul>
              </CardContent>
            </Card>

            {/* Skill Ratings */}
            <Card>
              <CardHeader>
                <CardTitle>Skill Ratings</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {skillRatings.map((item) => (
                    <div key={item.skill} className="flex justify-between items-center">
                      <span className="text-sm">{item.skill}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{item.rating}/5</span>
                        <div className="flex">
                          {[1,2,3,4,5].map((star) => (
                            <Star 
                              key={star} 
                              className={`w-4 h-4 ${
                                star <= Math.floor(item.rating) ? 'fill-yellow-400 text-yellow-400' : 'text-gray-300'
                              }`} 
                            />
                          ))}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Action Buttons */}
            <div className="flex gap-4">
              <Button variant="outline" className="flex-1">
                <Share className="w-4 h-4 mr-2" />
                Share
              </Button>
              <Button variant="outline" className="flex-1">
                <Download className="w-4 h-4 mr-2" />
                Download
              </Button>
              <Button 
                onClick={() => navigate('/dashboard')}
                className="flex-1 bg-green-600 hover:bg-green-700 text-white"
              >
                View Dashboard
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// Candidate Dashboard Component
function CandidateDashboard() {
  const navigate = useNavigate()
  
  const candidates = [
    { name: 'Rohit Sirewal', date: '17 Dec 2024', status: 'Completed', score: 90, communication: 'EXCELLENT', fit: 'STRONG', stage: 'PENDING REVIEW' },
    { name: 'Himanshu Dhamal', date: '18 Dec 2024', status: 'Completed', score: 67, communication: 'GOOD', fit: 'GOOD', stage: 'ON HOLD' },
    { name: 'Jeetendra JGH', date: '17 Dec 2024', status: 'Completed', score: 84, communication: 'GOOD', fit: 'GOOD', stage: 'PENDING REVIEW' },
    { name: 'Deepakala Dasgupta', date: '18 Dec 2024', status: 'Completed', score: 40, communication: 'GOOD', fit: 'GOOD', stage: 'PENDING REVIEW' }
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <h1 className="text-2xl font-bold text-gray-900">Content Manager</h1>
            </div>
            <Button className="bg-green-600 hover:bg-green-700 text-white">
              Try this interview yourself →
            </Button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Status Tabs */}
        <Tabs defaultValue="attended" className="mb-8">
          <TabsList className="grid w-full grid-cols-6">
            <TabsTrigger value="attended">ATTENDED (4)</TabsTrigger>
            <TabsTrigger value="invited">INVITED & PENDING (0)</TabsTrigger>
            <TabsTrigger value="starters">STARTERS (3)</TabsTrigger>
            <TabsTrigger value="declined">DECLINED (0)</TabsTrigger>
            <TabsTrigger value="not-qualified">NOT QUALIFIED (0)</TabsTrigger>
            <TabsTrigger value="retake">RETAKE REQUEST (1)</TabsTrigger>
          </TabsList>

          <TabsContent value="attended">
            {/* Top Performers */}
            <Card className="mb-8">
              <CardHeader>
                <CardTitle>Top Performers</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left py-3 px-4">Candidate Name</th>
                        <th className="text-left py-3 px-4">Interviewed on</th>
                        <th className="text-left py-3 px-4">Interview Status</th>
                        <th className="text-left py-3 px-4">Score %</th>
                        <th className="text-left py-3 px-4">Communication</th>
                        <th className="text-left py-3 px-4">Fit Level</th>
                        <th className="text-left py-3 px-4">Hiring Stage</th>
                        <th className="text-left py-3 px-4">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {candidates.map((candidate, index) => (
                        <tr key={index} className="border-b hover:bg-gray-50">
                          <td className="py-3 px-4">
                            <div className="flex items-center gap-3">
                              <Avatar className="w-8 h-8">
                                <AvatarFallback>{candidate.name.split(' ').map(n => n[0]).join('')}</AvatarFallback>
                              </Avatar>
                              {candidate.name}
                            </div>
                          </td>
                          <td className="py-3 px-4">{candidate.date}</td>
                          <td className="py-3 px-4">
                            <Badge variant="secondary">{candidate.status}</Badge>
                          </td>
                          <td className="py-3 px-4">
                            <Badge 
                              className={
                                candidate.score >= 80 ? 'bg-green-100 text-green-800' :
                                candidate.score >= 60 ? 'bg-yellow-100 text-yellow-800' :
                                'bg-red-100 text-red-800'
                              }
                            >
                              {candidate.score}%
                            </Badge>
                          </td>
                          <td className="py-3 px-4">
                            <Badge 
                              className={
                                candidate.communication === 'EXCELLENT' ? 'bg-green-100 text-green-800' :
                                'bg-blue-100 text-blue-800'
                              }
                            >
                              {candidate.communication}
                            </Badge>
                          </td>
                          <td className="py-3 px-4">
                            <Badge variant="outline">{candidate.fit}</Badge>
                          </td>
                          <td className="py-3 px-4">
                            <Select defaultValue={candidate.stage.toLowerCase().replace(' ', '-')}>
                              <SelectTrigger className="w-40">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="pending-review">PENDING REVIEW</SelectItem>
                                <SelectItem value="on-hold">ON HOLD</SelectItem>
                                <SelectItem value="hired">HIRED</SelectItem>
                                <SelectItem value="rejected">REJECTED</SelectItem>
                              </SelectContent>
                            </Select>
                          </td>
                          <td className="py-3 px-4">
                            <Button 
                              variant="outline" 
                              size="sm"
                              onClick={() => navigate('/report')}
                            >
                              View
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>

            {/* All Interview Responses */}
            <Card>
              <CardHeader>
                <div className="flex justify-between items-center">
                  <CardTitle>All Interview Responses (6)</CardTitle>
                  <div className="flex gap-4">
                    <div className="flex items-center gap-2">
                      <Search className="w-4 h-4" />
                      <Input placeholder="Search Candidates" className="w-48" />
                    </div>
                    <Button variant="outline">
                      <Filter className="w-4 h-4 mr-2" />
                      Filter
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="text-sm text-gray-600 mb-4">
                  Showing 1 of 1 Candidates
                </div>
                {/* Same table structure as above */}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}

// Main App Component
function App() {
  return (
    <Router>
      <div className="App">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/job-setup" element={<JobSetup />} />
          <Route path="/job-description" element={<JobDescription />} />
          <Route path="/interview" element={<InterviewInterface />} />
          <Route path="/coding-challenge" element={<CodingChallenge />} />
          <Route path="/report" element={<DetailedReport />} />
          <Route path="/dashboard" element={<CandidateDashboard />} />
        </Routes>
      </div>
    </Router>
  )
}

export default App

