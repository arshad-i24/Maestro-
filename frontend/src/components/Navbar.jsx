import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X, ArrowRight } from "lucide-react";

import logo from "../assets/images/maestro-logo1.png.png";

function Navbar() {
  const [activeSection, setActiveSection] = useState("home");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  const navigation = [
    {
      name: "Home",
      id: "home",
    },
    {
      name: "Features",
      id: "features",
    },
    {
      name: "Workflow",
      id: "workflow",
    },
    {
      name: "Technology",
      id: "technology",
    },
    {
      name: "Team",
      id: "team",
    },
  ];

  /* Detect scroll position */
  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20);
    };

    window.addEventListener("scroll", handleScroll);

    return () => {
      window.removeEventListener("scroll", handleScroll);
    };
  }, []);

  /* Detect active section */
  useEffect(() => {
    const sections = navigation
      .map((item) => document.getElementById(item.id))
      .filter(Boolean);

    const observer = new IntersectionObserver(
      (entries) => {
        const visibleSection = entries.find(
          (entry) => entry.isIntersecting
        );

        if (visibleSection) {
          setActiveSection(visibleSection.target.id);
        }
      },
      {
        rootMargin: "-35% 0px -55% 0px",
        threshold: 0,
      }
    );

    sections.forEach((section) => observer.observe(section));

    return () => {
      sections.forEach((section) => observer.unobserve(section));
    };
  }, []);

  /* Smooth scroll */
  const scrollToSection = (id) => {
    const section = document.getElementById(id);

    if (section) {
      section.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }

    setMobileOpen(false);
  };

  return (
    <motion.nav
      initial={{
        y: -80,
        opacity: 0,
      }}
      animate={{
        y: 0,
        opacity: 1,
      }}
      transition={{
        duration: 0.7,
        ease: "easeOut",
      }}
      className={`
        fixed
        top-0
        left-0
        z-50
        w-full
        transition-all
        duration-500
        ${
          scrolled
            ? "border-b border-white/10 bg-black/70 shadow-lg shadow-black/20 backdrop-blur-2xl"
            : "bg-black/30 backdrop-blur-xl"
        }
      `}
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3 md:px-8">

        {/* Logo */}
        <button
          onClick={() => scrollToSection("home")}
          className="flex items-center"
          aria-label="Go to homepage"
        >
          <img
            src={logo}
            alt="Maestro AI Logo"
            className="
              h-14
              w-auto
              object-contain
              transition-all
              duration-300
              hover:scale-105
            "
          />
        </button>

        {/* Desktop Navigation */}
        <div className="hidden items-center gap-8 md:flex">
          {navigation.map((item) => {
            const isActive = activeSection === item.id;

            return (
              <button
                key={item.id}
                onClick={() => scrollToSection(item.id)}
                className={`
                  relative
                  py-2
                  text-sm
                  font-medium
                  transition-all
                  duration-300
                  ${
                    isActive
                      ? "text-white"
                      : "text-gray-400 hover:text-white"
                  }
                `}
              >
                {item.name}

                {/* Active Indicator */}
                <span
                  className={`
                    absolute
                    -bottom-1
                    left-0
                    h-[2px]
                    rounded-full
                    bg-purple-400
                    transition-all
                    duration-300
                    ${
                      isActive
                        ? "w-full opacity-100"
                        : "w-0 opacity-0"
                    }
                  `}
                />
              </button>
            );
          })}
        </div>

        {/* Desktop CTA */}
        <motion.button
          whileHover={{
            scale: 1.04,
          }}
          whileTap={{
            scale: 0.97,
          }}
          onClick={() => scrollToSection("home")}
          className="
            hidden
            items-center
            gap-2
            rounded-xl
            bg-purple-600
            px-5
            py-2.5
            font-medium
            text-white
            transition-all
            duration-300
            hover:bg-purple-500
            hover:shadow-[0_0_30px_rgba(168,85,247,0.35)]
            md:flex
          "
        >
          Get Started
          <ArrowRight size={17} />
        </motion.button>

        {/* Mobile Menu Button */}
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="
            flex
            h-10
            w-10
            items-center
            justify-center
            rounded-xl
            border
            border-white/10
            bg-white/5
            text-gray-300
            transition-all
            duration-300
            hover:bg-white/10
            hover:text-white
            md:hidden
          "
          aria-label="Toggle navigation menu"
        >
          {mobileOpen ? (
            <X size={22} />
          ) : (
            <Menu size={22} />
          )}
        </button>

      </div>

      {/* Mobile Navigation */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{
              opacity: 0,
              height: 0,
            }}
            animate={{
              opacity: 1,
              height: "auto",
            }}
            exit={{
              opacity: 0,
              height: 0,
            }}
            transition={{
              duration: 0.25,
            }}
            className="
              overflow-hidden
              border-t
              border-white/10
              bg-black/90
              backdrop-blur-2xl
              md:hidden
            "
          >
            <div className="space-y-2 px-6 py-5">

              {navigation.map((item) => {
                const isActive =
                  activeSection === item.id;

                return (
                  <button
                    key={item.id}
                    onClick={() =>
                      scrollToSection(item.id)
                    }
                    className={`
                      flex
                      w-full
                      items-center
                      justify-between
                      rounded-xl
                      px-4
                      py-3
                      text-left
                      transition-all
                      duration-300
                      ${
                        isActive
                          ? "bg-purple-500/10 text-purple-300"
                          : "text-gray-400 hover:bg-white/5 hover:text-white"
                      }
                    `}
                  >
                    <span>{item.name}</span>

                    {isActive && (
                      <span className="h-2 w-2 rounded-full bg-purple-400" />
                    )}
                  </button>
                );
              })}

              {/* Mobile CTA */}
              <button
                onClick={() =>
                  scrollToSection("home")
                }
                className="
                  mt-3
                  flex
                  w-full
                  items-center
                  justify-center
                  gap-2
                  rounded-xl
                  bg-purple-600
                  px-5
                  py-3
                  font-medium
                  text-white
                  transition-all
                  duration-300
                  hover:bg-purple-500
                "
              >
                Get Started
                <ArrowRight size={17} />
              </button>

            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.nav>
  );
}

export default Navbar;