import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { FaMicrophone, FaRobot, FaCode, FaChartLine, FaUserShield, FaPlay, FaArrowRight } from 'react-icons/fa';
import Navbar from '../components/Navbar';
import { useInterview } from '../context/InterviewContext';
import { v4 as uuid } from 'uuid';
import { Button, FeatureCard } from '../components/ui';
import './Home.css';

/**
 * Professional Home page component with modern UI
 */
const Home = () => {
  const { userId, setUserId } = useInterview();
  const navigate = useNavigate();

  // Generate a user ID if not already set
  useEffect(() => {
    if (!userId) {
      setUserId(`user-${uuid()}`);
    }
  }, [userId, setUserId]);

  // Start the interview
  const handleStartInterview = () => {
    navigate('/interview');
  };

  return (
    <div className="home-page">
      <Navbar />
      
      {/* Hero Section */}
      <section className="hero-section">
        <div className="hero-container">
          <div className="hero-content">
            <div className="hero-text">
              <h1 className="hero-title">
                Master Technical Interviews 
                <span className="hero-title-accent"> with AI</span>
              </h1>
              
              <p className="hero-description">
                Prepare for your dream software engineering role with our AI-powered interview platform. 
                Get personalized feedback, practice real scenarios, and build confidence for success.
              </p>
              
              <div className="hero-actions">
                <Button
                  size="xl"
                  icon={<FaPlay />}
                  onClick={handleStartInterview}
                  className="hero-primary-btn"
                >
                  Start Interview Practice
                </Button>
                
                <Button
                  variant="ghost"
                  size="lg"
                  icon={<FaArrowRight />}
                  iconPosition="right"
                  className="hero-secondary-btn"
                >
                  Learn More
                </Button>
              </div>
            </div>
            
            <div className="hero-visual">
              <div className="hero-image-container">
                <img
                  src="https://images.unsplash.com/photo-1573164574572-cb89e39749b4?auto=format&fit=crop&q=80&w=800&h=600"
                  alt="Professional conducting technical interview"
                  className="hero-image"
                />
                <div className="hero-image-overlay">
                  <div className="floating-element element-1">
                    <FaRobot />
                    <span>AI-Powered</span>
                  </div>
                  <div className="floating-element element-2">
                    <FaCode />
                    <span>Live Coding</span>
                  </div>
                  <div className="floating-element element-3">
                    <FaChartLine />
                    <span>Real-time Feedback</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
      
      {/* Features Section */}
      <section className="features-section">
        <div className="features-container">
          <div className="features-header">
            <h2 className="features-title">
              Everything You Need to Succeed
            </h2>
            <p className="features-subtitle">
              Comprehensive interview preparation powered by advanced AI technology
            </p>
          </div>
          
          <div className="features-grid">
            <FeatureCard
              icon={<FaMicrophone />}
              title="Natural Voice Interface"
              description="Engage in natural conversations with advanced voice recognition and crystal-clear text-to-speech technology."
              variant="elevated"
            />
            
            <FeatureCard
              icon={<FaRobot />}
              title="Intelligent AI Interviewer"
              description="Experience adaptive questioning that evolves based on your responses and provides personalized coaching."
              variant="elevated"
            />
            
            <FeatureCard
              icon={<FaCode />}
              title="Live Coding Challenges"
              description="Solve real-world coding problems with instant feedback and optimization suggestions from our AI."
              variant="elevated"
            />
            
            <FeatureCard
              icon={<FaChartLine />}
              title="Progress Analytics"
              description="Track your improvement journey with detailed performance metrics and skill development insights."
              variant="elevated"
            />
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="how-it-works-section">
        <div className="how-it-works-container">
          <div className="how-it-works-header">
            <h2 className="how-it-works-title">
              How It Works
            </h2>
            <p className="how-it-works-subtitle">
              Get started in just a few simple steps
            </p>
          </div>
          
          <div className="steps-grid">
            <div className="step-card">
              <div className="step-number">1</div>
              <h3 className="step-title">Choose Your Role</h3>
              <p className="step-description">Select your target position and experience level</p>
            </div>
            
            <div className="step-card">
              <div className="step-number">2</div>
              <h3 className="step-title">Practice Interview</h3>
              <p className="step-description">Engage with our AI interviewer in realistic scenarios</p>
            </div>
            
            <div className="step-card">
              <div className="step-number">3</div>
              <h3 className="step-title">Get Feedback</h3>
              <p className="step-description">Receive detailed analysis and improvement suggestions</p>
            </div>
            
            <div className="step-card">
              <div className="step-number">4</div>
              <h3 className="step-title">Improve & Repeat</h3>
              <p className="step-description">Apply feedback and continue practicing until confident</p>
            </div>
          </div>
        </div>
      </section>
      
      {/* Call to Action Section */}
      <section className="cta-section">
        <div className="cta-container">
          <div className="cta-content">
            <h2 className="cta-title">
              Ready to Ace Your Next Interview?
            </h2>
            
            <p className="cta-description">
              Join thousands of developers who have improved their interview skills and landed their dream jobs.
            </p>
            
            <div className="cta-actions">
              <Button
                size="xl"
                onClick={handleStartInterview}
                className="cta-primary-btn"
              >
                Start Practicing Now
              </Button>
            </div>
            
            <div className="cta-stats">
              <div className="stat-item">
                <span className="stat-number">10,000+</span>
                <span className="stat-label">Interviews Conducted</span>
              </div>
              <div className="stat-item">
                <span className="stat-number">95%</span>
                <span className="stat-label">Success Rate</span>
              </div>
              <div className="stat-item">
                <span className="stat-number">500+</span>
                <span className="stat-label">Companies</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Development/Testing Section */}
      <section className="dev-section">
        <div className="dev-container">
          <div className="dev-divider"></div>
          <h3 className="dev-title">Development & Testing</h3>
          
          <div className="dev-actions">
            <Button
              variant="outline"
              size="sm"
              icon={<FaMicrophone />}
              onClick={() => navigate('/microphone-test')}
            >
              Microphone Test
            </Button>
            
            <Button
              variant="outline"
              size="sm"
              icon={<FaUserShield />}
              onClick={() => navigate('/face-auth-test')}
            >
              Face Authentication Test
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
};

export default Home; 