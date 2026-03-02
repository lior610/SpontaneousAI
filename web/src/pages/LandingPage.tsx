import { useNavigate, Link } from 'react-router-dom';
import { Sparkles, MapPin, Clock, Compass, ArrowRight, CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import heroMap from '@/assets/hero-map.png';

const features = [
  {
    icon: Sparkles,
    title: 'AI-Powered Planning',
    description: 'Smart recommendations based on your preferences and real-time data',
  },
  {
    icon: MapPin,
    title: 'Live Navigation',
    description: 'Seamless integration with Google Maps for turn-by-turn directions',
  },
  {
    icon: Clock,
    title: 'Real-Time Updates',
    description: 'Dynamic itinerary that adapts to your pace and changing conditions',
  },
];

const benefits = [
  'No more hours of research and planning',
  'Discover hidden gems and local favorites',
  'Personalized to your unique travel style',
  'Works offline with cached data',
];

export function LandingPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background overflow-hidden">
      {/* Hero Section */}
      <section className="relative min-h-screen flex flex-col">
        {/* Background gradient */}
        <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-background to-secondary/5" />
        
        {/* Floating decorations */}
        <div className="absolute top-20 left-10 w-20 h-20 bg-primary/10 rounded-full blur-2xl animate-float" />
        <div className="absolute bottom-40 right-10 w-32 h-32 bg-secondary/10 rounded-full blur-3xl animate-float" style={{ animationDelay: '1s' }} />
        <div className="absolute top-1/2 left-1/4 w-16 h-16 bg-accent/10 rounded-full blur-xl animate-float" style={{ animationDelay: '2s' }} />

        {/* Header */}
        <header className="relative z-10 flex items-center justify-between p-4 md:p-6 lg:px-12">
          <div className="flex items-center gap-2">
            <div className="w-10 h-10 rounded-xl bg-gradient-hero flex items-center justify-center">
              <Compass className="w-6 h-6 text-primary-foreground" />
            </div>
            <span className="text-xl font-bold text-gradient-hero">Spontaneous AI</span>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" asChild>
              <Link to="/login">Login</Link>
            </Button>
            <Button variant="default" size="sm" onClick={() => navigate('/wizard')}>
              Start Trip →
            </Button>
          </div>
        </header>

        {/* Main Hero Content */}
        <div className="relative z-10 flex-1 flex flex-col lg:flex-row items-center justify-center px-4 md:px-8 lg:px-16 py-8 gap-8 lg:gap-16">
          {/* Text Content */}
          <div className="max-w-xl text-center lg:text-left space-y-6 animate-slide-up">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-accent/10 text-accent text-sm font-medium">
              <Sparkles className="w-4 h-4" />
              AI-Powered Travel Planning
            </div>
            
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-extrabold leading-tight">
              Let AI plan your trip{' '}
              <span className="text-gradient-hero">in real time</span>
            </h1>
            
            <p className="text-lg md:text-xl text-muted-foreground leading-relaxed">
              No more endless planning. Just tell us what you love, and our AI creates 
              a dynamic travel route that adapts to you, the weather, and local events.
            </p>

            <div className="flex flex-col sm:flex-row items-center gap-4 pt-4">
              <Button 
                variant="hero" 
                size="xl"
                onClick={() => navigate('/wizard')}
                className="w-full sm:w-auto"
              >
                Start Your Trip
                <ArrowRight className="w-5 h-5 ml-2" />
              </Button>
            </div>

            {/* Quick Benefits */}
            <div className="pt-6 space-y-3">
              {benefits.map((benefit, i) => (
                <div 
                  key={benefit} 
                  className="flex items-center gap-2 text-sm text-muted-foreground animate-slide-up"
                  style={{ animationDelay: `${0.3 + i * 0.1}s` }}
                >
                  <CheckCircle2 className="w-4 h-4 text-secondary flex-shrink-0" />
                  <span>{benefit}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Hero Image */}
          <div className="relative w-full max-w-xl lg:max-w-2xl animate-scale-in" style={{ animationDelay: '0.2s' }}>
            <div className="relative rounded-2xl overflow-hidden shadow-2xl">
              <img 
                src={heroMap} 
                alt="AI-powered travel map with dynamic routes" 
                className="w-full h-auto"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-background/20 via-transparent to-transparent" />
            </div>
            
            {/* Floating cards */}
            <div className="absolute -bottom-4 -left-4 md:-left-8 bg-card rounded-xl p-3 shadow-lg border animate-float">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-full bg-secondary/20 flex items-center justify-center">
                  <MapPin className="w-4 h-4 text-secondary" />
                </div>
                <div>
                  <p className="text-xs font-semibold">Next Stop</p>
                  <p className="text-xs text-muted-foreground">Local Café 0.3km</p>
                </div>
              </div>
            </div>
            
            <div className="absolute -top-4 -right-4 md:-right-8 bg-card rounded-xl p-3 shadow-lg border animate-float" style={{ animationDelay: '1.5s' }}>
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center">
                  <Sparkles className="w-4 h-4 text-accent" />
                </div>
                <div>
                  <p className="text-xs font-semibold">AI Suggestion</p>
                  <p className="text-xs text-muted-foreground">Perfect for you!</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 px-4 md:px-8 lg:px-16 bg-muted/30">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">
              Travel smarter, not harder
            </h2>
            <p className="text-muted-foreground max-w-2xl mx-auto">
              Our AI combines your preferences with real-time data to create the perfect travel experience
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6 lg:gap-8">
            {features.map((feature, i) => (
              <div 
                key={feature.title}
                className="bg-card rounded-2xl p-6 shadow-card hover:shadow-lg transition-all duration-300 hover:-translate-y-1 animate-slide-up"
                style={{ animationDelay: `${i * 0.1}s` }}
              >
                <div className="w-12 h-12 rounded-xl bg-gradient-hero flex items-center justify-center mb-4">
                  <feature.icon className="w-6 h-6 text-primary-foreground" />
                </div>
                <h3 className="text-xl font-semibold mb-2">{feature.title}</h3>
                <p className="text-muted-foreground">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-4 md:px-8 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-hero opacity-10" />
        <div className="relative max-w-4xl mx-auto text-center">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            Ready for your spontaneous adventure?
          </h2>
          <p className="text-muted-foreground mb-8 text-lg">
            Join thousands of travelers who let AI handle the planning
          </p>
          <Button 
            variant="hero" 
            size="xl"
            onClick={() => navigate('/wizard')}
          >
            Start Planning Now
            <ArrowRight className="w-5 h-5 ml-2" />
          </Button>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-4 border-t bg-card/50">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Compass className="w-5 h-5 text-primary" />
            <span className="font-semibold">Spontaneous AI</span>
          </div>
          <p className="text-sm text-muted-foreground">
            © 2024 Spontaneous AI. Making travel effortless.
          </p>
        </div>
      </footer>
    </div>
  );
}
