package main

import (
	"fmt"
	"os"
)

type Server struct {
	port int
}

func (s *Server) Start() {
	fmt.Println("Starting server...")
}

func main() {
	fmt.Println("Hello Go!")
}
