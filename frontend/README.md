# AI Workforce Orchestration Frontend

A React-based frontend for the AI Workforce Orchestration System. Built with Vite, React Router, and Axios for a fast, responsive user experience.

## Prerequisites

- **Node.js** 16.0 or higher
- **npm** 7.0 or higher (or yarn/pnpm)
- Backend server running on `http://localhost:8000`

## Installation

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Start the development server:**
   ```bash
   npm run dev
   ```

   The frontend will be available at `http://localhost:3000`

## Build for Production

```bash
npm run build
```

This generates an optimized build in the `dist/` directory.

## Features

### 1. **Login Page**
- Token-based authentication
- Role selection (admin, employee, client)
- Credentials stored in localStorage for session persistence

### 2. **Dashboard**
- **Admin View**: Project overview, employee utilization metrics, task summaries
- **Employee View**: Assigned projects and tasks, workload visualization
- Quick navigation to assignments and decisions

### 3. **Employee Management**
- View all employees with their profiles
- Performance metrics (task completion rate, average duration)
- Availability status and assigned projects
- Skill and expertise tracking

### 4. **Task Management**
- Detailed task information and assignments
- Task progress tracking
- Required skills visualization
- Parent-child task hierarchies

### 5. **Decision Logs**
- View all AI assignment decisions
- Filter by confidence level, project, and date
- Analytics on decision distribution
- Override tracking and reasoning

### 6. **Navigation**
- Role-based menu items
- Quick links to all major sections
- Profile/logout functionality

## Project Structure

```
frontend/
├── src/
│   ├── App.jsx                 # Main app component with routing
│   ├── App.css                 # Global styles
│   ├── main.jsx                # React entry point
│   ├── components/
│   │   ├── Navbar.jsx          # Navigation component
│   │   ├── Dashboard.jsx       # Dashboard views
│   │   ├── EmployeeView.jsx    # Employee list and profiles
│   │   ├── TaskDetail.jsx      # Task information view
│   │   ├── Decisions.jsx       # Decision logs and analytics
│   │   └── [component].css     # Component-specific styles
│   └── constants/
│       └── config.js           # API configuration
├── index.html                  # HTML entry point
├── vite.config.js              # Vite configuration
├── package.json                # Dependencies
└── .gitignore                  # Git ignore rules
```

## API Integration

All API calls use the base URL: `http://localhost:8000`

### Authentication
Token-based authentication with Bearer token:
```javascript
const headers = {
  'Authorization': `Bearer ${localStorage.getItem('token')}`
};
```

### Key Endpoints
- `POST /auth/login` - User authentication
- `GET /employees/` - List all employees
- `GET /system/health` - Backend health check
- `GET /decisions/` - Decision history
- `POST /system/assign-task` - Create task assignment
- `GET /system/suggestions` - Get assignment suggestions

## Development

### Running with HMR (Hot Module Replacement)
The frontend automatically reloads when you make changes during development.

### API Testing
Test API connectivity by checking the browser console for any fetch/axios errors.

### Debugging
- Open DevTools (F12) for React Developer Tools
- Check the Network tab for API calls
- Use localStorage inspection to verify token storage

## Troubleshooting

### Port 3000 already in use
The Vite config will use the next available port if 3000 is taken (strictPort: false).

### CORS Errors
Ensure the backend is running and CORS is properly configured in FastAPI.

### API Connection Issues
- Verify backend is running on localhost:8000
- Check network tab in DevTools
- Verify API endpoints in components match backend routes

## Environment Variables

Create a `.env.local` file if needed:
```
VITE_API_URL=http://localhost:8000
```

(Currently hardcoded in components - can be refactored to use env vars)

## Performance

- **Vite**: ~500ms cold start, instant HMR
- **React**: Optimized component rendering with React 18
- **Axios**: Efficient HTTP client with interceptor support
- **CSS**: Global styles + component-scoped CSS for minimal overhead

## Future Enhancements

- [ ] WebSocket support for real-time updates
- [ ] Advanced filtering and search
- [ ] Export functionality (CSV/PDF)
- [ ] Dark mode theme
- [ ] Mobile-responsive improvements
- [ ] Accessibility (a11y) enhancements

## Links

- [Vite Documentation](https://vitejs.dev)
- [React Documentation](https://react.dev)
- [React Router Documentation](https://reactrouter.com)
- [Axios Documentation](https://axios-http.com)

## License

Part of the AI Workforce Orchestration System
