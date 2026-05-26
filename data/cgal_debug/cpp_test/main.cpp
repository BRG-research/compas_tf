// Test the CGAL-recommended pattern for consecutive booleans
// (EPICK mesh + EPECK vertex_point_map) on our dirty data.
//
// From: https://doc.cgal.org/6.2/PMP_Boolean_operations/
//       corefinement_consecutive_bool_op.cpp

#include <CGAL/Exact_predicates_inexact_constructions_kernel.h>
#include <CGAL/Exact_predicates_exact_constructions_kernel.h>
#include <CGAL/Surface_mesh.h>
#include <CGAL/Polygon_mesh_processing/corefinement.h>
#include <CGAL/IO/OFF.h>
#include <CGAL/Cartesian_converter.h>

#include <iostream>
#include <fstream>
#include <cmath>

typedef CGAL::Exact_predicates_inexact_constructions_kernel K;
typedef CGAL::Exact_predicates_exact_constructions_kernel EK;
typedef CGAL::Surface_mesh<K::Point_3> Mesh;
typedef boost::graph_traits<Mesh>::vertex_descriptor vertex_descriptor;
typedef Mesh::Property_map<vertex_descriptor, EK::Point_3> Exact_point_map;

namespace PMP = CGAL::Polygon_mesh_processing;
namespace params = CGAL::parameters;

// Exact vertex point map — the CGAL recommended pattern
struct Exact_vertex_point_map
{
    typedef boost::property_traits<Exact_point_map>::value_type value_type;
    typedef boost::property_traits<Exact_point_map>::reference reference;
    typedef boost::property_traits<Exact_point_map>::key_type key_type;
    typedef boost::read_write_property_map_tag category;

    Exact_point_map exact_point_map;
    Mesh* tm_ptr;
    CGAL::Cartesian_converter<K, EK> to_exact;
    CGAL::Cartesian_converter<EK, K> to_input;

    Exact_vertex_point_map() : tm_ptr(nullptr) {}

    Exact_vertex_point_map(const Exact_point_map& ep, Mesh& tm)
        : exact_point_map(ep), tm_ptr(&tm)
    {
        for (auto v : vertices(tm))
            exact_point_map[v] = to_exact(tm.point(v));
    }

    friend reference get(const Exact_vertex_point_map& map, key_type k)
    {
        return map.exact_point_map[k];
    }

    friend void put(const Exact_vertex_point_map& map, key_type k, const EK::Point_3& p)
    {
        map.exact_point_map[k] = p;
        map.tm_ptr->point(k) = map.to_input(p);
    }
};

bool load_off(const std::string& path, Mesh& mesh) {
    std::ifstream in(path);
    if (!in) return false;
    CGAL::IO::read_OFF(in, mesh);
    return mesh.number_of_vertices() > 0;
}

int main() {
    Mesh target, cutter;
    load_off("dirty_target.off", target);
    load_off("dirty_cutter.off", cutter);

    std::cout << "target: V=" << target.number_of_vertices()
              << " F=" << target.number_of_faces()
              << " closed=" << CGAL::is_closed(target) << std::endl;
    std::cout << "cutter: V=" << cutter.number_of_vertices()
              << " F=" << cutter.number_of_faces()
              << " closed=" << CGAL::is_closed(cutter) << std::endl;

    // Test 1: Raw EPICK (baseline — known to fail)
    {
        Mesh a = target, b = cutter, out;
        bool ok = PMP::corefine_and_compute_difference(a, b, out);
        std::cout << "\n1) Raw EPICK:          ok=" << ok
                  << " V=" << out.number_of_vertices()
                  << " F=" << out.number_of_faces() << std::endl;
    }

    // Test 2: CGAL recommended pattern — EPICK mesh + EPECK vertex_point_map
    {
        Mesh a = target, b = cutter, out;

        Exact_point_map a_epm = a.add_property_map<vertex_descriptor, EK::Point_3>("v:exact_point").first;
        Exact_point_map b_epm = b.add_property_map<vertex_descriptor, EK::Point_3>("v:exact_point").first;
        Exact_point_map o_epm = out.add_property_map<vertex_descriptor, EK::Point_3>("v:exact_point").first;

        Exact_vertex_point_map a_vpm(a_epm, a);
        Exact_vertex_point_map b_vpm(b_epm, b);
        Exact_vertex_point_map o_vpm(o_epm, out);

        bool ok = PMP::corefine_and_compute_difference(a, b, out,
            params::vertex_point_map(a_vpm),
            params::vertex_point_map(b_vpm),
            params::vertex_point_map(o_vpm));
        std::cout << "2) Hybrid EPICK+EPECK: ok=" << ok
                  << " V=" << out.number_of_vertices()
                  << " F=" << out.number_of_faces() << std::endl;
    }

    // Test 3: Pure EPECK (known to fail from earlier)
    {
        typedef CGAL::Surface_mesh<EK::Point_3> EMesh;
        EMesh a, b, out;

        // Load via EPICK then convert
        CGAL::Cartesian_converter<K, EK> to_exact;
        for (auto v : target.vertices())
            a.add_vertex(to_exact(target.point(v)));
        for (auto f : target.faces()) {
            std::vector<EMesh::Vertex_index> verts;
            for (auto v : vertices_around_face(target.halfedge(f), target))
                verts.push_back(EMesh::Vertex_index(v.idx()));
            a.add_face(verts[0], verts[1], verts[2]);
        }
        for (auto v : cutter.vertices())
            b.add_vertex(to_exact(cutter.point(v)));
        for (auto f : cutter.faces()) {
            std::vector<EMesh::Vertex_index> verts;
            for (auto v : vertices_around_face(cutter.halfedge(f), cutter))
                verts.push_back(EMesh::Vertex_index(v.idx()));
            b.add_face(verts[0], verts[1], verts[2]);
        }

        bool ok = PMP::corefine_and_compute_difference(a, b, out);
        std::cout << "3) Pure EPECK:         ok=" << ok
                  << " V=" << out.number_of_vertices()
                  << " F=" << out.number_of_faces() << std::endl;
    }

    // Test 4: Round to 12dp then raw EPICK
    {
        Mesh a = target, b = cutter, out;
        for (auto v : a.vertices()) {
            auto& p = a.point(v);
            p = K::Point_3(std::round(p[0]*1e12)/1e12, std::round(p[1]*1e12)/1e12, std::round(p[2]*1e12)/1e12);
        }
        for (auto v : b.vertices()) {
            auto& p = b.point(v);
            p = K::Point_3(std::round(p[0]*1e12)/1e12, std::round(p[1]*1e12)/1e12, std::round(p[2]*1e12)/1e12);
        }
        bool ok = PMP::corefine_and_compute_difference(a, b, out);
        std::cout << "4) Round 12dp + EPICK: ok=" << ok
                  << " V=" << out.number_of_vertices()
                  << " F=" << out.number_of_faces() << std::endl;
    }

    return 0;
}
